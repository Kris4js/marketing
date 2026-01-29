from typing import Optional
from pydantic import BaseModel

from src.agent.state import ReflectInput, ReflectionResult
from src.agent.prompts import (
    get_reflect_system_prompt,
    build_reflect_user_prompt,
)
from src.model.llm import llm_call
from src.utils.logger import logger


class ReflectionResponse(BaseModel):
    """Schema for the reflection response from the LLM."""

    isComplete: bool
    reasoning: str
    missingInfo: list[str] = []
    suggestedNextSteps: str = ""

    class Config:
        frozen = True


class ReflectPhase:
    """Reflect phase that evaluates if the task is complete.

    This phase analyzes the current plan, task results, and determines
    if enough information has been gathered to answer the query.
    """

    def __init__(
        self,
        model: str = "google/gemini-2.5-pro-preview-09-2025",
    ):
        self.model = model

    async def run(self, input: ReflectInput) -> ReflectionResult:
        """Evaluate if enough information has been gathered.

        Args:
            input (ReflectInput): Contains query, understanding, completed plans,
                                 task results, and iteration number

        Returns:
            ReflectionResult: Contains completion status, reasoning, and next steps
        """
        logger.info("Reflect phase: Evaluating task completion")

        system_prompt = get_reflect_system_prompt()
        user_prompt = build_reflect_user_prompt(
            query=input.query,
            understanding=input.understanding,
            completedPlans=input.completedPlans,
            taskResults=input.taskResults,
            iteration=input.iteration,
        )

        response = await llm_call(
            model=self.model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            response_format=ReflectionResponse,
        )

        # Parse the response into ReflectionResponse
        if isinstance(response, ReflectionResponse):
            reflection_response = response
        elif hasattr(response, "parsed"):
            reflection_response = response.parsed
        else:
            # Fallback: assume incomplete
            logger.warning(f"Unexpected response type: {type(response)}")
            reflection_response = ReflectionResponse(
                isComplete=False,
                reasoning="Unable to parse reflection response",
                missingInfo=[],
                suggestedNextSteps="",
            )

        reflection = ReflectionResult()
        reflection.isComplete = reflection_response.isComplete
        reflection.reasoning = reflection_response.reasoning
        reflection.missingInfo = reflection_response.missingInfo
        reflection.suggestedNextSteps = reflection_response.suggestedNextSteps

        logger.info(
            f"Reflect phase: Task complete={reflection.isComplete}, "
            f"reasoning={reflection.reasoning}"
        )

        return reflection
