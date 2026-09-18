"""Domain data types for the skill library."""

from collections.abc import Mapping
from dataclasses import dataclass

from httpskills.domain.errors import InvalidSkillName, ResourceNotContained

_NAME_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


@dataclass(frozen=True)
class SkillName:
    value: str

    def __post_init__(self) -> None:
        if not 1 <= len(self.value) <= 64:
            raise InvalidSkillName(self.value)
        if not set(self.value) <= _NAME_CHARACTERS:
            raise InvalidSkillName(self.value)
        if self.value.startswith("-") or self.value.endswith("-"):
            raise InvalidSkillName(self.value)
        if "--" in self.value:
            raise InvalidSkillName(self.value)


def _is_absolute_path(value: str) -> bool:
    if value.startswith("/") or value.startswith("\\"):
        return True
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return True
    return False


@dataclass(frozen=True)
class ResourcePath:
    value: str

    def __post_init__(self) -> None:
        if self.value == "" or _is_absolute_path(self.value):
            # The name of the skill is not known here; the caller (which does
            # know it) catches this and re-raises with the name filled in.
            raise ResourceNotContained(name="", path=self.value)


@dataclass(frozen=True)
class SkillSummary:
    name: SkillName
    description: str


@dataclass(frozen=True)
class SkillFrontmatter:
    name: SkillName
    description: str
    license: str | None
    compatibility: str | None
    allowed_tools: str | None
    metadata: Mapping[str, str]
    undefined_keys: Mapping[str, object]


@dataclass(frozen=True)
class Skill:
    frontmatter: SkillFrontmatter
    source_text: str


@dataclass(frozen=True)
class SkillCandidate:
    directory_name: str
    skill_md_text: str


@dataclass(frozen=True)
class ResolvedPair:
    skill_root: tuple[str, ...]
    target: tuple[str, ...]


ResolvedLocation = tuple[str, ...]
