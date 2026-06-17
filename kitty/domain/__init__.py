"""领域模型层：纯数据载体（Pydantic v2），不含任何业务逻辑或 SQL。

模型与流程分离的支点 —— Service 编排流程，Repository 读写库，本包只描述数据形状。
所有领域模型默认 frozen + extra=forbid，保证"改数据只能新增行"而非就地 mutate。
"""
