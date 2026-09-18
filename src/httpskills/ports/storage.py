"""The SkillStorage port: the domain's only contact with the outside."""

from collections.abc import Sequence
from typing import Protocol

from httpskills.domain.model import ResolvedLocation, ResolvedPair, SkillCandidate


class SkillStorage(Protocol):
    def list_candidates(self) -> Sequence[SkillCandidate]: ...

    def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair: ...

    def read_resource(self, location: ResolvedLocation) -> bytes: ...
