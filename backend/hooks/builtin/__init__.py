"""注册所有内置 hook。"""

from backend.hooks.builtin.iteration import on_iteration_start
from backend.hooks.builtin.persistence import on_iteration_end, on_loop_end
from backend.hooks.builtin.rollback import on_loop_error
from backend.hooks.builtin.sanitizer import on_before_model_request
from backend.hooks.builtin.system_prompt import on_loop_start
from backend.hooks.builtin.text_response import on_assistant_text_response
from backend.hooks.builtin.title import make_title_hook
from backend.hooks.builtin.tool_calls import on_tool_calls_detected
from backend.hooks.manager import Event, HookManager


def register_builtin_hooks(manager: HookManager, client) -> None:
    """注册所有内置 hook。

    `client` 是 OpenAI 客户端，title hook 需要它来调一次非流式模型生成标题。
    """
    manager.register(Event.LoopStart, on_loop_start)
    manager.register(Event.IterationStart, on_iteration_start)
    manager.register(Event.BeforeModelRequest, on_before_model_request)

    # AssistantTextResponse：text_response 必须先（先 yield done），title 后
    manager.register(Event.AssistantTextResponse, on_assistant_text_response)
    manager.register(Event.AssistantTextResponse, make_title_hook(client))

    manager.register(Event.ToolCallsDetected, on_tool_calls_detected)
    manager.register(Event.IterationEnd, on_iteration_end)
    manager.register(Event.LoopEnd, on_loop_end)
    manager.register(Event.LoopError, on_loop_error)


__all__ = ["register_builtin_hooks"]
