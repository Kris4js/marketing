from __future__ import annotations
import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    BaseMessage,
)
from typing import List

# 加载环境变量
# 注意：如果你的代码在容器中运行，确保 /app/.env 路径正确
load_dotenv(override=True)


def _get_chat_llm(
    model: str = "google/gemini-3-flash-preview",
    base_url: str = "https://openrouter.ai/api/v1",
) -> ChatOpenAI:
    """初始化并配置 LangChain ChatOpenAI 实例"""

    # 环境变量获取
    base_url = os.getenv("LLM_BINDING_HOST", base_url)
    api_key = os.getenv("LLM_BINDING_API_KEY", "")
    model_name = os.getenv("LLM_MODEL", model)

    if not api_key:
        raise ValueError(
            "LLM_BINDING_API_KEY environment variable is not set."
        )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        timeout=30,
        max_retries=1,
        temperature=0.0,
    )


def llm_call(
    prompt: str,
    system_prompt: str = "",
    model: str = "google/gemini-3-flash-preview",
) -> str:
    """
    Makes a call to the chat LLM with the given prompt.
    Args:
        prompt (str): 用户发送给 LLM 的提示。
        system_prompt (str): 可选的系统提示，用于指导 LLM 的行为。
    Returns:
        str: LLM 的响应文本。
    """
    llm = _get_chat_llm(model=model)

    messages: List[BaseMessage] = []

    # 1. 处理 System Prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))

    # 2. 处理 User Prompt
    messages.append(HumanMessage(content=prompt))

    # 调用 invoke 方法
    # 注意：LangChain 的 ChatModel.invoke 接受 BaseMessage 列表
    response: AIMessage = llm.invoke(messages)

    return response.content


def extract_xml(text: str, tag: str) -> str:
    """
    Extracts the content of the specified XML tag from the given text. Used for parsing structured responses

    Args:
        text (str): The text containing the XML.
        tag (str): The XML tag to extract content from.

    Returns:
        str: The content of the specified XML tag, or an empty string if the tag is not found.
    """
    match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""
