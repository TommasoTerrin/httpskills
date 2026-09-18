"""The SkillLibrary seam: the protocol's rules over a SkillStorage port."""

from collections.abc import Mapping

import yaml

from httpskills.domain.errors import (
    InvalidSkill,
    InvalidSkillName,
    ResourceNotContained,
    ResourceNotFound,
    SkillNotFound,
)
from httpskills.domain.model import (
    ResourcePath,
    Skill,
    SkillCandidate,
    SkillFrontmatter,
    SkillName,
    SkillSummary,
)
from httpskills.ports.storage import SkillStorage


def _summarise(candidate: SkillCandidate) -> SkillSummary:
    parts = candidate.skill_md_text.split("---\n", 2)
    if len(parts) != 3:
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="no frontmatter block",
        )
    frontmatter_text = parts[1]
    try:
        fields: Mapping[str, object] = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="frontmatter is not parseable YAML",
        ) from None
    if not isinstance(fields, Mapping) or fields.get("name") != candidate.directory_name:
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="declared name differs from the directory name",
        )
    description = fields.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="description is absent or not 1 to 1024 characters",
        )
    compatibility = fields.get("compatibility")
    if compatibility is not None and not isinstance(compatibility, str):
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="compatibility is not a string",
        )
    if isinstance(compatibility, str) and len(compatibility) > 500:
        raise InvalidSkill(
            directory_name=candidate.directory_name,
            reason="compatibility is longer than 500 characters",
        )
    if "metadata" in fields:
        metadata = fields["metadata"]
        if not isinstance(metadata, dict):
            raise InvalidSkill(
                directory_name=candidate.directory_name,
                reason="metadata is not a mapping",
            )
        for key, value in metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise InvalidSkill(
                    directory_name=candidate.directory_name,
                    reason="metadata is not a mapping of strings to strings",
                )
    return SkillSummary(
        name=SkillName(candidate.directory_name),
        description=description,
    )


_DEFINED_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "allowed-tools", "metadata"}
)


def _parse_frontmatter_fields(skill_md_text: str) -> Mapping[str, object]:
    parts = skill_md_text.split("---\n", 2)
    fields: Mapping[str, object] = yaml.safe_load(parts[1])
    return fields


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_str_mapping(value: object) -> Mapping[str, str]:
    if isinstance(value, Mapping):
        return {str(key): str(item) for key, item in value.items()}
    return {}


class SkillLibrary:
    def __init__(self, storage: SkillStorage) -> None:
        self._storage = storage

    def list_skills(self) -> tuple[SkillSummary, ...]:
        summaries = []
        for candidate in self._storage.list_candidates():
            try:
                summaries.append(_summarise(candidate))
            except (InvalidSkill, InvalidSkillName):
                continue
        return tuple(summaries)

    def get_skill(self, name: str) -> Skill:
        for candidate in self._storage.list_candidates():
            if candidate.directory_name != name:
                continue
            try:
                summary = _summarise(candidate)
            except (InvalidSkill, InvalidSkillName):
                raise SkillNotFound(name=name) from None
            fields = _parse_frontmatter_fields(candidate.skill_md_text)
            undefined_keys = {
                key: value
                for key, value in fields.items()
                if key not in _DEFINED_FRONTMATTER_KEYS
            }
            return Skill(
                frontmatter=SkillFrontmatter(
                    name=summary.name,
                    description=summary.description,
                    license=_as_optional_str(fields.get("license")),
                    compatibility=_as_optional_str(fields.get("compatibility")),
                    allowed_tools=_as_optional_str(fields.get("allowed-tools")),
                    metadata=_as_str_mapping(fields.get("metadata")),
                    undefined_keys=undefined_keys,
                ),
                source_text=candidate.skill_md_text,
            )
        raise SkillNotFound(name=name)

    def get_resource(self, name: str, path: str) -> bytes:
        for candidate in self._storage.list_candidates():
            if candidate.directory_name != name:
                continue
            try:
                summary = _summarise(candidate)
            except (InvalidSkill, InvalidSkillName):
                raise SkillNotFound(name=name) from None
            try:
                ResourcePath(path)
            except ResourceNotContained:
                raise ResourceNotContained(name=name, path=path) from None
            resolved = self._storage.resolve(candidate.directory_name, path)
            root_len = len(resolved.skill_root)
            if resolved.target[:root_len] != resolved.skill_root:
                raise ResourceNotContained(name=name, path=path)
            try:
                return self._storage.read_resource(resolved.target)
            except ResourceNotFound:
                raise ResourceNotFound(name=name, path=path) from None
        raise SkillNotFound(name=name)
