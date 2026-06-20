"""WorkspacePolicy：工作目录边界策略（替代旧 WORKDIR=Path.cwd() 隐式全局）。

把 safe_path 提为实例方法，由 create_app() 注入明确的工作根目录，
避免工具依赖进程 cwd。
"""

from __future__ import annotations

from pathlib import Path


class WorkspacePolicy:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def safe_path(self, rel: str) -> Path:
        """确保路径不逃逸工作目录。"""
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Path escapes workspace: {rel}")
        return path
