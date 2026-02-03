import frontmatter
from pathlib import Path

from src.skills.types import Skill, SkillMetadata, SkillSource


def parse_skill_file(content: str, path: str | Path, source: SkillSource) -> Skill:
    """
    Parse a SKILL.md file content into a Skill object.
    Extracts YAML frontmatter (name, description) and the markdown body (instructions).

    Args:
        content: Raw file content
        path: Absolute path to the file (for reference)
        source: Where this skill came from

    Returns:
        Parsed Skill object

    Raises:
        ValueError: If required frontmatter fields are missing
    """
    post = frontmatter.loads(content)
    data = post.metadata
    instructions = post.content

    # Validate required frontmatter fields
    if not data.get("name") or not isinstance(data.get("name"), str):
        raise ValueError(
            f"Skill at {path} is missing required 'name' field in frontmatter"
        )
    if not data.get("description") or not isinstance(data.get("description"), str):
        raise ValueError(
            f"Skill at {path} is missing required 'description' field in frontmatter"
        )

    return Skill(
        name=data["name"],
        description=data["description"],
        path=path,
        source=source,
        instructions=instructions.strip(),
    )


def load_skill_from_path(path: str | Path, source: SkillSource) -> Skill:
    """
    Load a skill from a file path.

    Args:
        path: Absolute path to the SKILL.md file
        source: Where this skill came from

    Returns:
        Parsed Skill object

    Raises:
        OSError: If file cannot be read
        ValueError: If file cannot be parsed
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return parse_skill_file(content, path, source)


def extract_skill_metadata(path: str | Path, source: SkillSource) -> SkillMetadata:
    """
    Extract just the metadata from a skill file without loading full instructions.
    Used for lightweight discovery at startup.

    Args:
        path: Absolute path to the SKILL.md file
        source: Where this skill came from

    Returns:
        Skill metadata (name, description, path, source)

    Raises:
        OSError: If file cannot be read
        ValueError: If file cannot be parsed
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    post = frontmatter.loads(content)
    data = post.metadata

    if not data.get("name") or not isinstance(data.get("name"), str):
        raise ValueError(
            f"Skill at {path} is missing required 'name' field in frontmatter"
        )
    if not data.get("description") or not isinstance(data.get("description"), str):
        raise ValueError(
            f"Skill at {path} is missing required 'description' field in frontmatter"
        )

    return SkillMetadata(
        name=data["name"],
        description=data["description"],
        path=path,
        source=source,
    )
