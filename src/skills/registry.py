from pathlib import Path
from typing import Optional

from src.skills.types import Skill, SkillMetadata, SkillSource
from src.skills.loader import load_skill_from_path, extract_skill_metadata

# Get the directory of this file to locate builtin skills
_CURRENT_DIR = Path(__file__).parent.resolve()

"""
Skill directories in order of precedence (later overrides earlier).
"""
# fmt: off
SKILL_DIRECTORIES: list[dict[str, object]] = [
    {"path": _CURRENT_DIR, "source": SkillSource.BUILTIN},
    {"path": Path.home() / ".dexter" / "skills", "source": SkillSource.USER}, 
    {"path": Path.cwd() / ".dexter" / "skills", "source": SkillSource.PROJECT}, 
] 
# fmt: on

# Cache for discovered skill (metadata only)
skill_metadata_cache: Optional[dict[str, SkillMetadata]] = None


def _scan_skill_directory(dir_path: Path, source: SkillSource) -> list[SkillMetadata]:
    """
    Scan a directory for SKILL.md files and return their metadata.
    Looks for directories containing SKILL.md files.

    Args:
        dir_path: Directory to scan
        source: Source type for discovered skills

    Returns:
        Array of skill metadata
    """
    if not dir_path.exists():
        return []

    skills: list[SkillMetadata] = []

    for entry in dir_path.iterdir():
        if entry.is_dir():
            skill_file_path = entry / "SKILL.md"
            if skill_file_path.exists():
                try:
                    metadata = extract_skill_metadata(str(skill_file_path), source)
                    skills.append(metadata)
                except Exception:
                    # Skip invalid skill files silently
                    pass

    return skills


def discover_skills() -> list[SkillMetadata]:
    """
    Discover all available skills from all skill directories.
    Later sources (project > user > builtin) override earlier ones.

    Returns:
        Array of skill metadata, deduplicated by name
    """
    global skill_metadata_cache

    if skill_metadata_cache is not None:
        return list(skill_metadata_cache.values())

    skill_metadata_cache = {}

    for skill_dir in SKILL_DIRECTORIES:
        path = skill_dir["path"]
        source = skill_dir["source"]
        skills = _scan_skill_directory(path, source)
        for skill in skills:
            # Later sources override earlier ones (by name)
            skill_metadata_cache[skill.name] = skill

    return list(skill_metadata_cache.values())


def get_skill(name: str) -> Optional[Skill]:
    """
    Get a skill by name, loading full instructions.

    Args:
        name: Name of the skill to load

    Returns:
        Full skill definition or None if not found
    """

    global skill_metadata_cache

    # Ensure cache is populated
    if skill_metadata_cache is None:
        discover_skills()

    metadata = skill_metadata_cache.get(name) if skill_metadata_cache else None
    if not metadata:
        return None

    # Load full skill with instructions
    return load_skill_from_path(metadata.path, metadata.source)


def build_skill_metadata_section() -> str:
    """
    Build the skill metadata section for the system prompt.
    Only includes name and description (lightweight).

    Returns:
        Formatted string for system prompt injection
    """
    skills = discover_skills()

    if len(skills) == 0:
        return "No skills available."

    return "\n".join(f"- **{s.name}**: {s.description}" for s in skills)


def clear_skill_cache() -> None:
    """Clear the skill cache. Useful for testing or when skills are added/removed."""
    global skill_metadata_cache
    skill_metadata_cache = None
