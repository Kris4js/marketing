import os

from dotenv import load_dotenv
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
)


load_dotenv()


DEFAULT_MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"


def _get_chat_llm(
    model: str = DEFAULT_MODEL,
    base_url: str = "https://openrouter.ai/api/v1",
) -> ChatOpenAI:
    """初始化并配置 LangChain ChatOpenAI 实例"""
    base_url = os.getenv("OPENAI_BASE_URL", base_url)
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=30,
    )


async def llm_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    tools: Optional[list] = None,
) -> AIMessage | str:
    """
    Makes a call to the chat LLM with the given prompt.
    Args:
        prompt (str): 用户发送给 LLM 的提示。
        system_prompt (str): 可选的系统提示，用于指导 LLM 的行为。
        tools (Optional[list]): 可选的工具列表，用于工具调用。
    Returns:
        AIMessage | str: 当 tools 存在时返回完整的 AIMessage 对象（包含 tool_calls），
                         否则仅返回响应文本内容。
    """
    llm = _get_chat_llm(model=model)

    messages: list[BaseMessage] = []

    # 1. 处理 System Prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 2. 处理 User Prompt
    messages.append(HumanMessage(content=prompt))

    # 3. 绑定 Tools
    if tools is not None:
        llm = llm.bind_tools(tools)

    # 4. 调用 LLM
    response: AIMessage = await llm.ainvoke(messages)

    # 5. 返回带工具调用的完整响应
    if tools is not None:
        return response

    return response


async def llm_call_with_structured_output(
    prompt: str,
    system_prompt: Optional[str] = None,
    output_schema: Optional[type] = None,
    model: str = DEFAULT_MODEL,
):
    """
    Makes a call to the chat LLM with the given prompt and returns structured output.
    Args:
        prompt (str): 用户发送给 LLM 的提示。
        system_prompt (str): 可选的系统提示，用于指导 LLM 的行为。
        output_schema (type): 用于结构化输出的 Pydantic 模型类。
    Returns:
        Any: LLM 的结构化响应。
    """
    llm = _get_chat_llm(model=model)

    messages: list[BaseMessage] = []

    # 1. 处理 System Prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 2. 处理 User Prompt
    messages.append(HumanMessage(content=prompt))

    # 3. 声明 Response Schema
    llm_with_structured_output = llm.with_structured_output(
        output_schema, method="json_mode"
    )

    response: AIMessage = await llm_with_structured_output.ainvoke(messages)

    return response


async def llm_stream_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL,
):
    """
    Makes a streaming call to the chat LLM with the given prompt.
    Args:
        prompt (str): 用户发送给 LLM 的提示。
        system_prompt (str): 可选的系统提示，用于指导 LLM 的行为。
    Returns:
        Async generator: LLM 的响应流。
    """
    llm = _get_chat_llm(model=model)

    messages: list[BaseMessage] = []

    # 1. 处理 System Prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 2. 处理 User Prompt
    messages.append(HumanMessage(content=prompt))

    # 3. 调用 LLM 流式响应
    async for chunk in llm.astream(messages):
        # Extract content from the chunk
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
        # Skip empty chunks (metadata only)


async def llm_stream_call_with_structured_output(
    prompt: str,
    system_prompt: Optional[str] = None,
    output_schema: Optional[type] = None,
    model: str = "google/gemini-2.5-flash-lite-preview-09-2025",
):
    """
    Makes a streaming call to the chat LLM with the given prompt and returns structured output.
    Args:
        prompt (str): 用户发送给 LLM 的提示。
        system_prompt (str): 可选的系统提示，用于指导 LLM 的行为。
        output_schema (type): 用于结构化输出的 Pydantic 模型类。
    Returns:
        Async generator: LLM 的结构化响应流。
    """
    llm = _get_chat_llm(model=model)

    messages: list[BaseMessage] = []

    # 1. 处理 System Prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 2. 处理 User Prompt
    messages.append(HumanMessage(content=prompt))

    # 3. 声明 Response Schema
    llm_with_structured_output = llm.with_structured_output(
        output_schema, method="json_mode"
    )

    # 4. 调用 LLM 流式响应
    async for chunk in await llm_with_structured_output.astream(messages):
        yield chunk
