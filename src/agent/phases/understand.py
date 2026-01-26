import configparser

from pathlib import Path
from typing import Optional, override, TypeAlias
from pydantic import BaseModel, Field

from ..state import Understanding, UnderstandInput
from ..prompts import get_understand_system_prompt, build_understand_user_prompt
from ...model.llm import llm_call_with_structured_output
from .base import Phase, EntitySchema


_config_file = Path(__file__).parent.parent.parent / "config.ini"
_config = configparser.ConfigParser()
_config.read(_config_file)


class UnderstandingSchema(BaseModel):
    """Schema for the understanding output from the LLM."""

    intent: str = Field(
        ...,
        description="A clear statement of what the user wants to accomplish.",
    )
    entities: list[EntitySchema] = Field(
        ..., description="Key entities extracted from the query."
    )


UnderstandingOutput: TypeAlias = UnderstandingSchema


class UnderstandPhase(Phase):
    def __init__(
        self,
        model: Optional[str] = _config.get(
            "understand", "model", fallback="google/gemini-3-flash-preview"
        ),
    ):
        self.model = model

    @override
    async def run(self, input: UnderstandInput) -> Understanding:
        """_summary_

        Args:
            input (UnderstandInput): _description_

        Returns:
            Understanding: _description_
        """
        # Build conversation context if available
        # TODO 先实现 Memory 逻辑，然后再实现添加历史对话
        conversation_context = None
        if input.conversation_history:
            ...

        # Build the prompt
        systemPrompt = get_understand_system_prompt()
        userPrompt = build_understand_user_prompt(
            query=input.query,
            conversation_context=conversation_context,
        )

        # Call LLM with structured output
        response = await llm_call_with_structured_output(
            prompt=userPrompt,
            system_prompt=systemPrompt,
            model=self.model,
            output_schema=UnderstandingSchema,
        )

        return response
