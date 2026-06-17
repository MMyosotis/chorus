"""Repository 层：各自数据表的唯一 SQL 入口。

职责边界：
- 只承 SQL 与行↔模型映射，不持锁、不缓存、不做业务校验；
- 不互相依赖，统一通过 ConnectionFactory 拿 sqlite 连接；
- 对外返回 Pydantic 模型（kitty.domain.models），不返回裸 dict / tuple。
"""
