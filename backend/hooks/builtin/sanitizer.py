"""BeforeModelRequest hook：清洗 history 为可发给 OpenAI 的消息列表。"""

from backend.hooks.manager import AgentContext


def on_before_model_request(ctx: AgentContext):
    """剥离自定义 _meta_* 字段，写入 ctx.provider_messages。"""
    ctx.provider_messages = [
        {k: v for k, v in m.items() if not k.startswith("_meta_")}
        for m in ctx.conv["history"]
    ]
    return None
