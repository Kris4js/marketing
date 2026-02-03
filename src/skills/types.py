from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class SkillSource(Enum):
    """
    Source of a skill definition.
     - builtin: Shipped with Dexter (src/skills/builtin/)
     - user: User-level skills (~/.dexter/skills/)
     - project: Project-level skills (.dexter/skills/)
    """

    BUILTIN = "builtin"
    USER = "user"
    PROJECT = "project"


class SkillMetadata(BaseModel):
    name: str = Field(..., description="The name of the skill.")
    description: str = Field(..., description="A brief description of the skill.")
    path: str | Path = Field(
        ..., description="The file absolute path to the SKILL.md file."
    )
    source: SkillSource = Field(..., description="The source of the skill definition.")


class Skill(SkillMetadata):
    instructions: str = Field(
        ...,
        description="The full markdown content of the skill definition.",
    )
