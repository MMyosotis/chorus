"""Service 层：业务编排。

职责：编排 Repository 完成业务规则（锁、缓存、清理、provider_messages 构建、
agent loop 等），不直接写 SQL（经 Repository），不感知 HTTP（由 routes 适配）。
"""
