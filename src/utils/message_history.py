"""
MessageHistory 将消息历史完全记录在内存中，在应用程序重新启动时清除。

  - 保存摘要
  - 选择相关消息历史
  - 加载完整消息内容

> https://github.com/virattt/dexter/blob/00e1aa69/src/utils/message-history.ts#L1-L189
"""

import hashlib
import json

from loguru import logger
from dataclasses import dataclass
from pydantic import BaseModel, Field

from ..model.llm import llm_call, llm_call_with_structured_output
from ..agent.prompts import (
    MESSAGE_SUMMARY_SYSTEM_PROMPT,
    MESSAGE_SELECTION_SYSTEM_PROMPT,
)


# 代表一个对话回合（查询 + 回答 + 摘要）
@dataclass
class Message:
    id: int
    query: str
    answer: str
    summary: str  # LLM-generated summary of the answer


class SelectedMessagesSchema(BaseModel):
    message_ids: list[int] = Field(
        ..., description="List of relevant message IDs (0-indexed)"
    )


# 管理多轮对话的内存中对话历史记录
# 存储用户查询、最终答案和 LLM 生成的摘要
# 遵循与 ToolContextManager 类似的模式
class MessageHistory:
    def __init__(self, model: str) -> None:
        self.messages: list[Message] = []
        self.model = model
        self.relevantMessagesByQuery: dict[str, list[Message]] = {}

    def _hash_query(self, query: str) -> str:
        """
        Generate a 12-character MD5 hash of the query.

        Args:
            query: Input string to hash

        Returns:
            First 12 characters of MD5 hex digest

        Example:
            >>> hash_query("hello world")
            '5eb63bbbe01e'
        """
        return hashlib.md5(query.encode()).hexdigest()[:12]

    def set_model(self, model: str) -> None:
        self.model = model

    async def generate_summary(self, query: str, answer: str) -> str:
        """
        Generate a summary for the given query and answer using an LLM.

        Args:
            query: User's query
            answer: LLM's answer

        Returns:
            Summary string
        """

        answer_preview = answer[:1500]  # Limit for prompt size

        prompt = f"""Query: {query}
Answer: {answer_preview}

Generate a brief 1-2 sentence summary of this answer.
"""

        try:
            response = await llm_call(
                prompt=prompt,
                system_prompt=MESSAGE_SUMMARY_SYSTEM_PROMPT,
                model=self.model,
            )
            # NOTE Debug  
            logger.debug(f"Generated summary: {response}")

            return response.strip()

        except Exception:
            return f"Answer to: {query[:100]}"

    async def add_message(self, query: str, answer: str) -> None:
        """
        Add a new message (query + answer) to the history, generating a summary.

        Args:
            query: User's query
            answer: LLM's answer

        Returns:
            Message object with ID, query, answer, and summary
        """
        # Clear the relevant messages cache as history has changed
        self.relevantMessagesByQuery.clear()

        summary = await self.generate_summary(query, answer)
        logger.debug(f"Adding message to history: query={query}, summary={summary}")

        self.messages.append(
            Message(
                id=len(self.messages),
                query=query,
                answer=answer,
                summary=summary,
            )
        )

    async def select_relevant_messages(
        self, current_query: str
    ) -> list[Message]:
        """
        Uses LLM to select which messages are relevant to the current query.
        Results are cached by query hash to avoid redundant LLM calls within the same query.

        Args:
            current_query: The current user query

        Returns:
            List of relevant Message objects
        """
        if len(self.messages) == 0:
            return []

        # Check cache first
        cacheKey = self._hash_query(current_query)
        cached = self.relevantMessagesByQuery.get(cacheKey)
        if cached is not None:
            return cached

        messages_info = [
            {
                "id": message.id,
                "query": message.query,
                "summary": message.summary,
            } for message in self.messages
        ]  # fmt: skip

        prompt = f"""Current user query: {current_query}

Previous Conversations:
{json.dumps(messages_info, ensure_ascii=False, indent=2)}

Select which previous messages are relevant to understanding or answering the current query.
"""

        try:
            response = await llm_call_with_structured_output(
                prompt=prompt,
                system_prompt=MESSAGE_SELECTION_SYSTEM_PROMPT,
                model=self.model,
                output_schema=SelectedMessagesSchema,
            )

            selected_ids = (
                response["message_ids"]
                if isinstance(response, dict) and isinstance(response.get("message_ids"), list)
                else []
            )  # fmt: skip

            selected_messages = [
                self.messages[idx]
                for idx in selected_ids
                if isinstance(idx, int) and 0 <= idx < len(self.messages)
            ]

            # Cache the result
            self.relevantMessagesByQuery[cacheKey] = selected_messages

            return selected_messages

        except Exception:
            # On failure, return empty (don't inject potentially irrelevant context)
            return []

    def format_for_planning(self, messages: list[Message]) -> str:
        """
        Format selected messages for inclusion in planning prompts.

        Args:
            messages: List of Message objects

        Returns:
            Formatted string with each message's query and summary
        """
        if len(messages) == 0:
            return ""

        return "\n\n".join(
            f"User: {message.query}\nAssistant: {message.summary}"
            for message in messages
        )

    def get_messages(self) -> list[Message]:
        """
        Get the full list of messages in history.

        Returns:
            List of Message objects
        """
        return self.messages.copy()

    def get_user_messages(self) -> list[str]:
        """
        Get the list of user queries in history.

        Returns:
            List of user query strings
        """
        return [message.query for message in self.messages]

    def has_messages(self) -> bool:
        """
        Check if there are any messages in history.

        Returns:
            True if there are messages, False otherwise
        """
        return len(self.messages) > 0

    def clear(self) -> None:
        """
        Clear all messages from history.
        """
        self.messages.clear()
        self.relevantMessagesByQuery.clear()
