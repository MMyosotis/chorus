"""重建产品库：drop_all 后 create_all，清空 data/chorus.db 全部表。

demo 项目结构变动时直接重建（不保留旧数据）；正常运行不会调用。
"""
from __future__ import annotations

from chorus.config import DATA_DIR
from chorus.repo.engine import build_engine
from chorus.repo.models import Base


def main() -> None:
    engine = build_engine(DATA_DIR / "chorus.db")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print(f"已重建 {DATA_DIR / 'chorus.db'}")


if __name__ == "__main__":
    main()
