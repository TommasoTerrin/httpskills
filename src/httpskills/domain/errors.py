"""Errors of the skill library. All derive from SkillLibraryError."""

from dataclasses import dataclass


class SkillLibraryError(Exception):
    """Base of every error the skill library raises."""


@dataclass
class SkillNotFound(SkillLibraryError):
    """ERR-001: no Valid Skill carries this name."""

    name: str


@dataclass
class ResourceNotFound(SkillLibraryError):
    """ERR-002: the resolved location is inside the skill, but nothing readable is there."""

    name: str
    path: str


@dataclass
class ResourceNotContained(SkillLibraryError):
    """ERR-003: the path is absolute or empty, or resolves outside the skill's root."""

    name: str
    path: str


@dataclass
class InvalidSkill(SkillLibraryError):
    """A stored candidate is not a Valid Skill. Internal: never escapes a seam."""

    directory_name: str
    reason: str


@dataclass
class InvalidSkillName(SkillLibraryError):
    """A string cannot be a Skill Name. Internal: never escapes a seam."""

    value: str
