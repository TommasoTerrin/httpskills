"""Filesystem adapter for the SkillStorage port."""

from collections.abc import Sequence
from pathlib import Path

from httpskills.domain.errors import ResourceNotFound
from httpskills.domain.model import ResolvedLocation, ResolvedPair, SkillCandidate


class FilesystemSkillStorage:
    def __init__(self, skills_root: Path) -> None:
        self._skills_root = skills_root

    def list_candidates(self) -> Sequence[SkillCandidate]:
        candidates: list[SkillCandidate] = []
        for entry in sorted(self._skills_root.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            candidates.append(
                SkillCandidate(
                    directory_name=entry.name,
                    skill_md_text=skill_md.read_text(encoding="utf-8"),
                )
            )
        return candidates

    def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair:
        skill_root_path = (self._skills_root / directory_name).resolve()
        target_path = (skill_root_path / relative_path).resolve()
        return ResolvedPair(skill_root=skill_root_path.parts, target=target_path.parts)

    def read_resource(self, location: ResolvedLocation) -> bytes:
        target_path = Path(*location)
        if not target_path.is_file():
            raise ResourceNotFound(name="", path=str(target_path))
        return target_path.read_bytes()
