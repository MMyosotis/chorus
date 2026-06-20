"""领域层：按业务概念扁平组织，每个模块同放该概念的数据模型 + 纯操作。

与流程分离的支点 —— services/ + hooks/ 编排流程，repositories/ 读写库，本包只描述
数据形状与不碰基础设施的纯规则。所有 Pydantic 模型默认 frozen + extra=forbid，
保证"改数据只能新增行"而非就地 mutate。零基础设施依赖（不 import repositories /
tools / openai / threading）。
"""
