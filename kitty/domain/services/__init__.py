"""领域服务：跨对象的纯领域逻辑（零基础设施依赖）。

与顶层 services/（application 编排层，碰 repo/OpenAI/锁）的区别：
本包只接受领域模型入参、返回领域模型或纯数据结构，不 import
repositories / tools / openai / threading。便于独立单测。
"""
