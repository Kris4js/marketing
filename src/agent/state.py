from __future__ import annotations

from enum import Enum
from typing import Any, Optional

# ======================================================================
## Phase Types
# ======================================================================


class Phase(Enum):
    UNDERSTAND = "understand"
    PLAN = "plan"
    EXECUTE = "execute"
    REFLECT = "reflect"
    ANSWER = "answer"
    COMPLETE = "complete"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(Enum):
    USE_TOOLS = "use_tools"
    REASON = "reason"


# ======================================================================
## Entity Types
# ======================================================================


class EntityType(Enum): 
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    TIME = "time"
    MONEY = "money"
    PERCENT = "percent"
    EVENT = "event"
    WORK_OF_ART = "work_of_art"
    LAW = "law"
    LANGUAGE = "language"


class Entity:
    type: EntityType
    value: str


# ======================================================================
## Understanding Phase Types
# ======================================================================


class UnderstandInput:
    query: str
    conversation_history: Optional[Any]  # TODO Build a history middleware


class Understanding:
    intent: str
    entities: list[Entity]


class ToolCall:
    tool: str
    args: dict[str, Any]


class ToolCallStatus(ToolCall):
    status: TaskStatus


# ======================================================================
## Plan Phase Types
# ======================================================================


class Task:
    id: str
    description: str
    status: TaskStatus
    taskType: Optional[TaskType]
    toolCalls: Optional[list[ToolCallStatus]]
    dependsOn: Optional[list[str]]


class Plan:
    summary: str
    tasks: list[Task]


class PlanInput:
    query: str
    understanding: Understanding
    priorPlans: Optional[list[Plan]]
    priorResults: Optional[dict[str, TaskResult]]
    guidanceFromReflection: Optional[str]


# ======================================================================
## Execute Phase Types
# ======================================================================


class TaskResult:
    taskId: str
    output: Optional[str]


class ExecuteInput:
    query: str
    task: Task
    plan: Plan
    contextData: str


# ======================================================================
## Summary of a tool call result which keep in context
# ======================================================================


class ToolSummary:
    id: str
    toolName: str
    args: dict[str, Any]


# ======================================================================
## Agent State
# ======================================================================


class AgentState:
    query: str
    currentPhase: Phase
    understanding: Optional[Understanding]
    plan: Optional[Plan]
    taskResults: dict[str, TaskResult]
    currentTaskId: Optional[str]


def create_initial_state(query: str) -> AgentState:
    return AgentState(
        query=query,
        currentPhase=Phase.UNDERSTAND,
        taskResults={},
    )


# ======================================================================
## Reflection Phase Types
# ======================================================================


class ReflectInput:
    query: str
    understanding: Understanding
    completedPlans: list[Plan]
    taskResults: dict[str, TaskResult]
    iteration: int


class ReflectionResult:
    isComplete: bool
    reasoning: str
    missingInfo: list[str]
    suggestedNextSteps: str


# ======================================================================
## Answer Phase Types
# ======================================================================


class AnswerInput:
    query: str
    completedPlans: list[Plan]
    taskResults: dict[str, TaskResult]
