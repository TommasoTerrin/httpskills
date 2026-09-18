"""BR-3 (no caching, no memoisation) for the SkillLibrary seam."""

from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from httpskills.domain.library import SkillLibrary


@dataclass(frozen=True)
class FakeSkillCandidate:
    """What the SkillStorage port yields: a directory name and a raw SKILL.md."""

    directory_name: str
    skill_md_text: str


class MutableFakeSkillStorage:
    """In-memory substitute for SkillStorage whose candidates can change after construction.

    `candidates` is a plain attribute, reassignable by the test between two calls
    to `list_skills()`, so it can prove the library re-reads storage every time
    rather than remembering the first answer.
    """

    def __init__(self, candidates: Sequence[object]) -> None:
        self.candidates = list(candidates)

    def list_candidates(self) -> Sequence[object]:
        return self.candidates

    def resolve(self, directory_name: str, relative_path: str) -> object:
        raise AssertionError("resolve must not be reached while listing skills")

    def read_resource(self, location: tuple[str, ...]) -> bytes:
        raise AssertionError("read_resource must not be reached while listing skills")


# AC-FEAT-001-033
def test_second_list_skills_call_reflects_candidates_changed_after_the_first_call() -> None:
    """list_skills() re-reads storage on every call instead of caching the first result.

    One SkillLibrary is built over one fake storage. The first call sees
    "skill-a" and must report it. Then, on the same fake instance and the same
    library instance, the storage's candidates are swapped for "skill-b" alone.
    A second call must reflect "skill-b" and must no longer carry "skill-a" — a
    cached first answer would still show "skill-a" here, so this is the only
    shape of test that can catch memoisation (BR-3).
    """
    skill_a = FakeSkillCandidate(
        directory_name="skill-a",
        skill_md_text=(
            "---\n"
            "name: skill-a\n"
            "description: The first candidate the storage yields.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    skill_b = FakeSkillCandidate(
        directory_name="skill-b",
        skill_md_text=(
            "---\n"
            "name: skill-b\n"
            "description: The second candidate the storage yields.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    storage = MutableFakeSkillStorage([skill_a])
    library = SkillLibrary(storage)

    first = [summary.name.value for summary in library.list_skills()]
    assert first == ["skill-a"]

    storage.candidates = [skill_b]

    second = [summary.name.value for summary in library.list_skills()]
    assert second == ["skill-b"]
    assert "skill-a" not in second


# AC-FEAT-001-035
def test_second_get_skill_call_raises_not_found_after_candidates_changed_underneath_it() -> None:
    """get_skill(name) re-reads storage on every call instead of caching the first result.

    One SkillLibrary is built over one fake storage holding "skill-a". The first
    call to get_skill("skill-a") must succeed. Then, on the same fake instance
    and the same library instance, the storage's candidates are swapped so that
    "skill-a" no longer resolves. A second call to get_skill("skill-a") must
    raise SkillNotFound — a cached first answer would still return the Skill
    here, so this is the only shape of test that can catch memoisation for
    get_skill specifically (BR-3), rather than for list_skills alone.
    """
    skill_a = FakeSkillCandidate(
        directory_name="skill-a",
        skill_md_text=(
            "---\n"
            "name: skill-a\n"
            "description: The first candidate the storage yields.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    skill_b = FakeSkillCandidate(
        directory_name="skill-b",
        skill_md_text=(
            "---\n"
            "name: skill-b\n"
            "description: The second candidate the storage yields.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    storage = MutableFakeSkillStorage([skill_a])
    library = SkillLibrary(storage)

    first = library.get_skill("skill-a")
    assert first.frontmatter.name.value == "skill-a"

    storage.candidates = [skill_b]

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_skill("skill-a")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "a second get_skill call after the candidates changed underneath it must "
        f"signal a miss with SkillNotFound; it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "skill-a", (
        "SkillNotFound carries a `name` field holding the name that was asked for; "
        f"it held {getattr(raised, 'name', None)!r}"
    )
