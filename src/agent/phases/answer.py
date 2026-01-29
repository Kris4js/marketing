from typing import Optional

from src.agent.state import AnswerInput
from src.agent.prompts import get_answer_system_prompt, build_answer_user_prompt
from src.model.llm import llm_call
from src.agent.phases.base import Phase
from src.utils.logger import logger


class AnswerPhase(Phase):
    """Answer phase that synthesizes final response.

    This phase takes all completed plans and task results and generates
    a comprehensive answer to the user's query.
    """

    def __init__(
        self,
        model: str = "google/gemini-2.5-pro-preview-09-2025",
    ):
        self.model = model

    async def run(self, input: AnswerInput) -> str:
        """Generate final answer from all completed work.

        Args:
            input (AnswerInput): Contains query, completed plans, and task results

        Returns:
            str: The final answer to the user's query
        """
        logger.info("Answer phase: Generating final response")

        system_prompt = get_answer_system_prompt()
        user_prompt = build_answer_user_prompt(
            query=input.query,
            completedPlans=input.completedPlans,
            taskResults=input.taskResults,
        )

        response = await llm_call(
            model=self.model,
            prompt=user_prompt,
            system_prompt=system_prompt,
        )

        # Normalize response to string
        output = response.content if hasattr(response, "content") else str(response)

        logger.info("Answer phase: Final response generated")

        return output
