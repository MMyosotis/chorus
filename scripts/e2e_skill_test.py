#!/usr/bin/env python3
"""E2E 平台 Skill 加载：确定性验证 6213c62 新增的 Skill 子文件读取链路。

覆盖：
- /api/skills/{name}/files/{path} 路由正向读 SKILL.md / references / preview / platform.yaml；
- 404 边界：不存在技能、不存在文件、非白名单后缀；
- media_type 按 SUFFIX_MEDIA_TYPES 单源派生；
- load_skill 工具的 path 参数：读 references/script.md 成功，非法 path 返 Reply；
- SkillLoader.read_file 路径越界逃逸返 None（路由层 URL 规范化难测越界，下沉到 loader 直调）；
- PostCard meta 闭环：parse_postcard_md 解析出 meta.preview_ref/stylesheet_ref，拆成 name/path
  能被 SkillLoader.read_file 读回（前端 PlatformPreviewShell 渲染契约的源头）。

不调真实 LLM，临时库隔离且跑完自动清理，不写 data/chorus.db。
"""

import atexit
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import chorus.app as app_module
from chorus.domain.skill.loader import SKILLS_DIR, SkillLoader, SUFFIX_MEDIA_TYPES
from chorus.domain.task.markdown import parse_postcard_md
from chorus.tools.framework import Reply, ToolContext
from chorus.tools.builtin.load_skill import LoadSkillTool

_tmp = Path(tempfile.mkdtemp())
atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))
with patch.object(app_module, "DATA_DIR", _tmp):
    _app = app_module.create_app()

_client = TestClient(_app)
_loader = SkillLoader()
_load_skill = LoadSkillTool(_loader)

_VERDICTS = []


def _check(name, ok, note=""):
    verdict = "OK" if ok else "FAIL"
    mark = {"OK": "✓", "FAIL": "✗"}[verdict]
    line = f"  [{mark}] {name}"
    if note:
        line += f"  ({note})"
    print(line)
    _VERDICTS.append(verdict)


def _get(name, path):
    return _client.get(f"/api/skills/{name}/files/{path}")


# ---- 路由正向：各子文件可读，media_type 正确 ----
print("=" * 60)
print("[路由正向] web-blog 各子文件")

cases = [
    ("web-blog", "SKILL.md", "text/markdown"),
    ("web-blog", "references/planning.md", "text/markdown"),
    ("web-blog", "references/script.md", "text/markdown"),
    ("web-blog", "references/image.md", "text/markdown"),
    ("web-blog", "references/finalize.md", "text/markdown"),
    ("web-blog", "preview/desktop.html", "text/html"),
    ("web-blog", "preview/desktop.css", "text/css"),
    ("web-blog", "platform.yaml", "text/yaml"),
]
for name, path, expected_mime in cases:
    resp = _get(name, path)
    ct = resp.headers.get("content-type", "").split(";")[0]
    _check(f"GET {name}/{path} -> 200", resp.status_code == 200,
           f"实际 {resp.status_code}")
    _check(f"  media_type={expected_mime}", ct == expected_mime,
           f"实际 {ct!r}")
    _check(f"  正文非空", bool(resp.text.strip()),
           f"{len(resp.text)} 字符")

# ---- 404 边界 ----
print("\n[404 边界]")

resp = _get("nonexistent-skill", "SKILL.md")
_check("不存在技能 -> 404", resp.status_code == 404, f"实际 {resp.status_code}")

resp = _get("web-blog", "references/missing.md")
_check("不存在文件 -> 404", resp.status_code == 404, f"实际 {resp.status_code}")

resp = _get("web-blog", "preview/desktop.js")
_check("非白名单后缀(.js) -> 404", resp.status_code == 404, f"实际 {resp.status_code}")

resp = _get("web-blog", "preview/desktop.txt")
_check("非白名单后缀(.txt) -> 404", resp.status_code == 404, f"实际 {resp.status_code}")

# ---- load_skill 工具 path 参数 ----
print("\n[load_skill 工具] path 参数")

ctx = ToolContext(session_id="skill-e2e")
result = _load_skill.run({"name": "web-blog", "path": "references/script.md"}, ctx)
_check("带 path 读 references/script.md -> Reply",
       isinstance(result.outcome, Reply), type(result.outcome).__name__)
_check("  回传含文案官参考内容", "文案" in result.outcome.content or "正文" in result.outcome.content,
       f"前 40 字 {result.outcome.content[:40]!r}")

result = _load_skill.run({"name": "web-blog"}, ctx)
_check("不带 path 默认读 SKILL.md -> Reply",
       isinstance(result.outcome, Reply) and "网页博客" in result.outcome.content,
       f"前 40 字 {result.outcome.content[:40]!r}")

result = _load_skill.run({"name": "web-blog", "path": "references/missing.md"}, ctx)
_check("非法 path -> Reply(not found)", isinstance(result.outcome, Reply)
       and "not found" in result.outcome.content, result.outcome.content[:60])

result = _load_skill.run({"name": "nope", "path": "SKILL.md"}, ctx)
_check("不存在技能 -> Reply(not found)", isinstance(result.outcome, Reply)
       and "not found" in result.outcome.content, result.outcome.content[:60])

# ---- SkillLoader.read_file 路径越界逃逸 ----
print("\n[SkillLoader] 路径越界逃逸拦截")

leaked = _loader.read_file("web-blog", "../../config.py")
_check("../ 逃逸返 None", leaked is None, f"实际 {type(leaked).__name__}")

leaked = _loader.read_file("web-blog", "../../../pyproject.toml")
_check("深层逃逸返 None", leaked is None, f"实际 {type(leaked).__name__}")

valid = _loader.read_file("web-blog", "references/finalize.md")
_check("包内合法路径返内容", valid is not None and "preview_ref" in valid,
       f"{len(valid or '')} 字符")

# ---- PostCard meta 引用闭环 ----
print("\n[PostCard meta 闭环] 解析出的资源引用可被 loader 读回")

postcard_md = (
    "<!-- preview_ref: web-blog/preview/desktop.html -->\n"
    "<!-- stylesheet_ref: web-blog/preview/desktop.css -->\n\n"
    "# 春节档观影指南\n\n## 票房看点\n\n今年春节档竞争激烈。\n\n#标签：#春节档 #电影"
)
parsed = parse_postcard_md(postcard_md)
meta = parsed["meta"]
_check("meta.preview_ref 解析正确",
       meta["preview_ref"] == "web-blog/preview/desktop.html", repr(meta.get("preview_ref")))
_check("meta.stylesheet_ref 解析正确",
       meta["stylesheet_ref"] == "web-blog/preview/desktop.css", repr(meta.get("stylesheet_ref")))


def _split_ref(ref):
    """复刻前端 PlatformPreviewShell.resolveResource 的拆分：技能名 / 包内路径。"""
    parts = str(ref).split("/", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


preview_name, preview_path = _split_ref(meta["preview_ref"])
stylesheet_name, stylesheet_path = _split_ref(meta["stylesheet_ref"])
html = _loader.read_file(preview_name, preview_path)
css = _loader.read_file(stylesheet_name, stylesheet_path)
_check("preview_ref 经拆分可被 loader 读回", html is not None and "<section" in html,
       f"{len(html or '')} 字符")
_check("stylesheet_ref 经拆分可被 loader 读回", css is not None and ".pc-" in css,
       f"{len(css or '')} 字符")

# ---- SKILLS_DIR 落点确认（单源）----
print("\n[单源] SKILLS_DIR 指向源码 resources/skills")
_check("SKILLS_DIR 末两段 = resources/skills",
       SKILLS_DIR.parts[-2:] == ("resources", "skills"), str(SKILLS_DIR))
_check("web-blog 技能目录存在", (SKILLS_DIR / "web-blog" / "SKILL.md").is_file(), "")

# ---- 汇总 ----
print("\n" + "=" * 60)
ok = sum(1 for v in _VERDICTS if v == "OK")
fail = sum(1 for v in _VERDICTS if v == "FAIL")
print(f"E2E 平台 Skill 加载结论: {ok} 通过 / {fail} 失败  ->  "
      f"{'全部通过 ✓' if fail == 0 else '存在失败 ✗'}")
sys.exit(0 if fail == 0 else 1)
