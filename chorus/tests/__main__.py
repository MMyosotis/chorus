"""一键跑全部测试：逐个 import 各 test_*.py 模块并调用其 main()（裸跑风格，不依赖 pytest）。

任一模块失败即打印 traceback 并以非零退出；全部通过打印汇总。
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import traceback


def main():
    import chorus.tests as pkg
    failures: list[str] = []
    passed = 0
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        name = mod_info.name
        if not name.startswith("test_"):
            continue
        full = f"chorus.tests.{name}"
        try:
            mod = importlib.import_module(full)
            mod.main()
            passed += 1
        except Exception:
            failures.append(full)
            traceback.print_exc()
    print(f"\n==== 汇总：{passed} 个模块通过，{len(failures)} 个失败 ====")
    if failures:
        for f in failures:
            print(f"  FAIL {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
