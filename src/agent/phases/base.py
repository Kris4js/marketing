from typing import Any
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from ..state import EntityType


class Phase(ABC):
    model: str

    @abstractmethod
    async def run(self, input: str) -> Any:
        pass


class EntitySchema(BaseModel):
    type: EntityType = Field(..., description="The type of the entity.")
    value: str = Field(..., description="The raw value from the query.")
