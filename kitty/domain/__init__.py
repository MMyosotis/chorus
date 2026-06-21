"""领域层：按业务概念扁平组织，每个模块同放该概念的数据模型 + 纯操作
+ 围绕该单一概念的基础设施型 service。

与流程分离的支点 —— services/ + hooks/ 编排流程，repositories/ 读写库，本包只描述
数据形状与不碰跨概念流程的规则。所有 Pydantic 模型默认 frozen + extra=forbid，
保证"改数据只能新增行"而非就地 mutate。不 import repositories / services / hooks，
但允许直接持有围绕自身概念的外部依赖（文件系统 / openai / threading / urllib）。
"""
