"""memory 路由 HTTP 适配层测试：4 端点状态码与透传。

只断言适配行为（不存在->404 / 参数缺失->422 / 正常透出 service 返回），最小 app + fake service。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chorus.domain.memory.models import CreatorMemory
from chorus.routes.memory import router as memory_router
from chorus.routes.providers import provide_memory_service


def _mk(memory_id="m1", description="d", kind="performance"):
    return CreatorMemory(
        id=memory_id, description=description, content="c",
        platform=["xhs"], visible_to=["supervisor"], kind=kind,
        created_at=1.0, updated_at=2.0,
    )


class FakeMemoryService:
    """脚本化 stub：按方法记入参，返预设值；update/delete 不存在时返 None/静默。"""

    def __init__(self):
        self.list_result: list[CreatorMemory] = []
        self.created: list[tuple] = []
        self.updated: list[tuple] = []
        self.deleted: list[str] = []
        self.update_result = _mk()
        self.update_missing: set[str] = set()

    def list_all(self):
        return self.list_result

    def create_memory(self, description, content, platform, visible_to, kind="reference"):
        self.created.append((description, content, tuple(platform), tuple(visible_to), kind))
        return _mk(description=description, kind=kind)

    def update_memory(self, memory_id, description, content, platform, visible_to, kind):
        self.updated.append((memory_id, description, content, tuple(platform), tuple(visible_to), kind))
        if memory_id in self.update_missing:
            return None
        return self.update_result

    def delete_memory(self, memory_id):
        self.deleted.append(memory_id)


def _client(fake: FakeMemoryService) -> TestClient:
    app = FastAPI()
    app.include_router(memory_router)
    app.dependency_overrides[provide_memory_service] = lambda: fake
    return TestClient(app)


def test_list_memories_ok():
    fake = FakeMemoryService()
    fake.list_result = [_mk("a"), _mk("b")]
    r = _client(fake).get("/api/memory")
    assert r.status_code == 200
    assert len(r.json()["memories"]) == 2
    assert r.json()["memories"][0]["id"] == "a"


def test_create_memory_ok():
    fake = FakeMemoryService()
    r = _client(fake).post("/api/memory", json={
        "description": "偏好", "content": "正文",
        "platform": ["xhs"], "visible_to": ["supervisor"], "kind": "performance",
    })
    assert r.status_code == 200
    assert r.json()["description"] == "偏好"
    assert fake.created == [("偏好", "正文", ("xhs",), ("supervisor",), "performance")]


def test_create_memory_defaults_to_reference():
    """未传 kind 默认参考记忆。"""
    fake = FakeMemoryService()
    r = _client(fake).post("/api/memory", json={"description": "d", "content": "c"})
    assert r.status_code == 200
    assert fake.created[0][4] == "reference"


def test_create_memory_invalid_kind_422():
    """kind 非 performance/reference -> 422，不触达 service。"""
    fake = FakeMemoryService()
    r = _client(fake).post("/api/memory", json={"description": "d", "content": "c", "kind": "medium"})
    assert r.status_code == 422
    assert fake.created == []


def test_create_memory_missing_fields_422():
    """缺必填 description -> 422。"""
    fake = FakeMemoryService()
    r = _client(fake).post("/api/memory", json={"content": "c"})
    assert r.status_code == 422


def test_put_memory_ok():
    fake = FakeMemoryService()
    r = _client(fake).put("/api/memory/m1", json={
        "description": "改后", "content": "c",
        "platform": ["xhs"], "visible_to": ["supervisor"], "kind": "performance",
    })
    assert r.status_code == 200
    assert fake.updated[0][0] == "m1"
    assert fake.updated[0][1] == "改后"


def test_put_memory_not_found_404():
    fake = FakeMemoryService()
    fake.update_missing = {"m9"}
    r = _client(fake).put("/api/memory/m9", json={
        "description": "x", "content": "c",
        "platform": [], "visible_to": [], "kind": "reference",
    })
    assert r.status_code == 404


def test_put_memory_missing_fields_422():
    """缺必字段 -> 422，不触达 service。"""
    fake = FakeMemoryService()
    r = _client(fake).put("/api/memory/m1", json={"description": "d"})
    assert r.status_code == 422
    assert fake.updated == []


def test_delete_memory_ok():
    fake = FakeMemoryService()
    r = _client(fake).delete("/api/memory/m1")
    assert r.status_code == 200
    assert r.json()["id"] == "m1"
    assert fake.deleted == ["m1"]


def test_delete_memory_idempotent():
    """删除不存在的也返 200（幂等）。"""
    fake = FakeMemoryService()
    r = _client(fake).delete("/api/memory/none")
    assert r.status_code == 200


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
