"""Listing behaviour of the SkillLibrary seam, driven by a fake SkillStorage."""

from collections.abc import Iterator, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, fields, is_dataclass

import pytest

from httpskills.domain.library import SkillLibrary


def _every_string_reachable_from(value: object, seen: set[int] | None = None) -> Iterator[str]:
    """Yield every string reachable from `value`, however it is nested or wrapped.

    "Anywhere in the response" is taken literally: the whole returned structure is
    walked rather than the two fields the summary is known to carry today. A field
    added later — of any type, at any depth, inside a tuple, a mapping, a dataclass
    or a plain object — cannot smuggle a Body past this walk. Objects that are none
    of those shapes surrender their `repr` and `str`, so even a custom type holding
    the text is read.
    """
    seen = set() if seen is None else seen
    if id(value) in seen:
        return
    seen.add(id(value))

    if isinstance(value, str):
        yield value
        return
    if isinstance(value, (bytes, bytearray)):
        yield value.decode("utf-8", errors="replace")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _every_string_reachable_from(key, seen)
            yield from _every_string_reachable_from(item, seen)
        return
    if isinstance(value, (Sequence, AbstractSet)):
        for item in value:
            yield from _every_string_reachable_from(item, seen)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from _every_string_reachable_from(getattr(value, field.name, None), seen)
        yield repr(value)
        return

    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        yield from _every_string_reachable_from(dict(attributes), seen)
    for slot in getattr(type(value), "__slots__", ()):
        yield from _every_string_reachable_from(getattr(value, slot, None), seen)
    yield repr(value)
    yield str(value)


@dataclass(frozen=True)
class FakeSkillCandidate:
    """What the SkillStorage port yields: a directory name and a raw SKILL.md.

    The two field names are the contract's; nothing else is carried, because the
    port is forbidden to hand the domain anything it could read from.
    """

    directory_name: str
    skill_md_text: str


class FakeSkillStorage:
    """In-memory substitute for the SkillStorage port.

    Only `list_candidates` is exercised by the catalogue read path; the other
    two operations fail loudly so an accidental call is visible.
    """

    def __init__(self, candidates: Sequence[object]) -> None:
        self._candidates = tuple(candidates)

    def list_candidates(self) -> Sequence[object]:
        return self._candidates

    def resolve(self, directory_name: str, relative_path: str) -> object:
        raise AssertionError("resolve must not be reached while listing skills")

    def read_resource(self, location: tuple[str, ...]) -> bytes:
        raise AssertionError("read_resource must not be reached while listing skills")


# AC-FEAT-001-004
def test_ac_feat_001_004_skills_root_without_any_skill_directory_lists_nothing() -> None:
    """A skills root holding no skill directory yields an empty catalogue.

    The storage yields no candidate at all. The contract fixes the answer as the
    empty tuple, and fixes that list_skills never raises.
    """
    library = SkillLibrary(FakeSkillStorage([]))

    assert library.list_skills() == ()


# AC-FEAT-001-022
def test_ac_feat_001_022_skill_declaring_only_the_two_required_fields_is_catalogued() -> None:
    """A frontmatter carrying `name` and `description` and nothing else is valid.

    Every optional field of the Agent Skills specification is absent. The skill
    must still reach the catalogue, and its summary must carry the two values the
    frontmatter declared.
    """
    skill_md = (
        "---\n"
        "name: pdf-processing\n"
        "description: Extracts text and tables from PDF files.\n"
        "---\n"
        "\n"
        "Run pdftotext before attempting to parse any table.\n"
    )
    candidate = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=skill_md,
    )

    summaries = SkillLibrary(FakeSkillStorage([candidate])).list_skills()

    assert len(summaries) == 1
    assert summaries[0].name.value == "pdf-processing"
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-016
def test_ac_feat_001_016_skill_whose_declared_name_differs_from_its_directory_is_excluded() -> None:
    """A skill declaring a name other than its directory's is not in the catalogue.

    The Agent Skills specification requires the declared `name` to equal the name
    of the containing directory, so `demo-skill` declaring `other-name` is not a
    Valid Skill. Per BR-1 the catalogue read still succeeds and simply drops it —
    a sound skill offered alongside proves the drop is the mismatch's doing and
    not the whole read collapsing.
    """
    mismatched = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: other-name\n"
            "description: Declares a name that is not its directory's.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )

    summaries = SkillLibrary(FakeSkillStorage([mismatched, sound])).list_skills()

    catalogued = [summary.name.value for summary in summaries]
    assert "other-name" not in catalogued
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]


# AC-FEAT-001-017
@pytest.mark.parametrize(
    "malformed_name",
    [
        pytest.param("", id="empty"),
        pytest.param("a" * 65, id="longer-than-64-characters"),
        pytest.param("Demo-Skill", id="uppercase-letters"),
        pytest.param("-demo", id="leading-hyphen"),
        pytest.param("demo-", id="trailing-hyphen"),
        pytest.param("demo--skill", id="consecutive-hyphens"),
    ],
)
def test_ac_feat_001_017_skill_whose_name_breaks_the_name_format_is_excluded(
    malformed_name: str,
) -> None:
    """A name the Agent Skills specification forbids keeps the skill out of the catalogue.

    The specification allows a name of 1 to 64 characters drawn from a-z, 0-9 and
    '-', neither starting nor ending with '-' and never carrying '--'. Each case
    here breaks exactly one of those rules and nothing else: the directory name is
    the declared name, so the mismatch rule (AC-016) cannot be what excludes it.

    Per BR-1 the read still succeeds and drops the offender silently. The sound
    skill offered alongside proves the drop is the name's doing rather than the
    whole catalogue read collapsing.
    """
    malformed = FakeSkillCandidate(
        directory_name=malformed_name,
        skill_md_text=(
            "---\n"
            f'name: "{malformed_name}"\n'
            "description: Declares a name the specification forbids.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )

    summaries = SkillLibrary(FakeSkillStorage([malformed, sound])).list_skills()

    catalogued = [summary.name.value for summary in summaries]
    assert malformed_name not in catalogued
    assert catalogued == ["pdf-processing"]


# AC-FEAT-001-018
@pytest.mark.parametrize(
    "description_line",
    [
        pytest.param("", id="key-absent"),
        pytest.param('description: ""\n', id="empty"),
        pytest.param(f'description: "{"d" * 1025}"\n', id="longer-than-1024-characters"),
    ],
)
def test_ac_feat_001_018_skill_whose_description_breaks_the_length_rule_is_excluded(
    description_line: str,
) -> None:
    """A description outside 1 to 1024 characters keeps the skill out of the catalogue.

    `description` is required by the Agent Skills specification and must hold
    between 1 and 1024 characters. The three cases break that in the three ways it
    can be broken: the key missing entirely, the key present but empty, and a value
    of 1025 characters. Nothing else is wrong — each declares a well-formed name
    equal to its directory's, so neither AC-016 nor AC-017 can be what excludes it.

    The skill offered alongside carries a description of exactly 1024 characters,
    which the specification allows. It pins the upper boundary from below — 1024 in,
    1025 out — and, per BR-1, proves the read still succeeds and drops the offender
    silently rather than collapsing.
    """
    longest_allowed_description = "p" * 1024

    offender = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: demo-skill\n"
            f"{description_line}"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            f'description: "{longest_allowed_description}"\n'
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )

    summaries = SkillLibrary(FakeSkillStorage([offender, sound])).list_skills()

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == longest_allowed_description


# AC-FEAT-001-019
@pytest.mark.parametrize(
    "skill_md_text",
    [
        pytest.param(
            "# Demo Skill\n\nPlain markdown with no fences, so no metadata block at all.\n",
            id="no-frontmatter-at-all",
        ),
        pytest.param(
            '---\nname: demo-skill\ndescription: "unterminated\n---\n\nBody text.\n',
            id="malformed-yaml-unclosed-quote",
        ),
        pytest.param(
            "---\nname: demo-skill\nmetadata:\n\tauthor: someone\n---\n\nBody text.\n",
            id="malformed-yaml-tab-indented-mapping",
        ),
        pytest.param(
            "---\nname: demo-skill\ndescription: Fine so far.\n: : :\n---\n\nBody text.\n",
            id="malformed-yaml-line-that-is-not-a-key-value",
        ),
    ],
)
def test_ac_feat_001_019_candidate_with_absent_or_unparseable_frontmatter_is_excluded_without_raising(
    skill_md_text: str,
) -> None:
    """A SKILL.md with no frontmatter, or with unparseable YAML, is dropped silently.

    Two shapes of broken input are covered. The first carries no `---` fences at
    all, so there is no metadata block to read. The other three carry the fences
    but hold YAML that no parser can load: an unterminated double-quoted scalar, a
    tab-indented mapping, and a line that is not a key/value pair. Each of those
    three was checked against a YAML load and does raise — a string merely believed
    to be broken but which YAML happily accepts would make this test prove nothing.
    Which parser the implementation picks is not frozen, so the text is fixed here
    and the parser is not named.

    The half of the criterion that is easy to under-test is the second: a parser
    raises on malformed input and that exception must not reach the caller. The
    contract fixes `list_skills` as never raising (BR-1), so the escape is caught
    and reported explicitly rather than left to surface as an error. The sound
    skill offered alongside carries the assertion further than "did not raise":
    the read must still complete and still return what it owes.
    """
    broken = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=skill_md_text,
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([broken, sound]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the point of the criterion
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-021
@pytest.mark.parametrize(
    "metadata_block",
    [
        pytest.param("metadata:\n  - author\n  - version\n", id="sequence-not-a-mapping"),
        pytest.param("metadata: just-a-string\n", id="scalar-not-a-mapping"),
        pytest.param("metadata:\n  version: 1.0\n", id="value-is-a-number"),
        pytest.param("metadata:\n  stable: yes\n", id="value-is-a-boolean"),
        pytest.param(
            "metadata:\n  author:\n    name: Example Org\n",
            id="value-is-a-nested-mapping",
        ),
        pytest.param("metadata:\n  1: one\n", id="key-is-a-number"),
    ],
)
def test_ac_feat_001_021_skill_whose_metadata_is_not_a_string_to_string_mapping_is_excluded(
    metadata_block: str,
) -> None:
    """A `metadata` that is not a mapping of strings to strings keeps the skill out.

    `metadata` is optional, but the Agent Skills specification fixes its shape when
    it is declared: a map of string keys to string values. The cases break that in
    the two ways it can break, and cover both.

    Not a mapping at all: declared as a sequence, and declared as a bare scalar.
    A mapping whose entries are not strings: a value YAML loads as a float, a value
    YAML loads as a boolean, a value that is itself a mapping, and a key YAML loads
    as an integer. The float and the boolean are the cases that matter most, because
    `1.0` and `yes` read as strings in the file and are not strings after parsing —
    an implementation that trusts the file's appearance rather than the parsed value
    passes every other case and fails these two.

    Nothing else is wrong with any offender: each declares a well-formed name equal
    to its directory's and a description inside 1 to 1024 characters, so none of
    AC-016, AC-017 or AC-018 can be what excludes it.

    The companion skill declares the same two suspicious values *quoted*, so YAML
    loads them as the strings they look like. It is what makes this test prove the
    rule discriminates: `version: "1.0"` in, `version: 1.0` out. Per BR-1 the read
    still succeeds and drops the offender silently, so an escaping exception is
    reported as a failure of this criterion rather than left to surface as an error.
    """
    offender = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: demo-skill\n"
            "description: Declares a metadata that is not a string-to-string mapping.\n"
            f"{metadata_block}"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "metadata:\n"
            "  author: Example Org\n"
            '  version: "1.0"\n'
            '  stable: "yes"\n'
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([offender, sound]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-023
def test_ac_feat_001_023_skill_declaring_every_optional_field_well_formed_is_catalogued() -> None:
    """A frontmatter carrying all four optional fields, each well-formed, is valid.

    The Agent Skills specification defines exactly four optional fields, and this
    frontmatter declares all of them at once: `license` as a short string,
    `compatibility` as a string of exactly 500 characters — the longest the
    specification allows, which pins the upper bound from below — `metadata` as a
    mapping whose keys and values are all strings, and `allowed-tools` as a
    space-separated list of tool names, which the domain does not interpret.

    The criterion is the mirror image of AC-022: the optional fields are allowed,
    not merely tolerated, so the skill must be *present* rather than merely not
    crash the read. Presence alone would be a weak assertion — a skill whose
    optional fields were mistaken for part of its identity could survive the read
    with a mangled summary — so the two fields the summary carries are pinned to
    the literals the frontmatter declared.
    """
    longest_allowed_compatibility = "c" * 500
    skill_md = (
        "---\n"
        "name: pdf-processing\n"
        "description: Extracts text and tables from PDF files.\n"
        "license: Apache-2.0\n"
        f'compatibility: "{longest_allowed_compatibility}"\n'
        "metadata:\n"
        "  author: Example Org\n"
        '  version: "1.4.0"\n'
        "allowed-tools: Read Grep Glob\n"
        "---\n"
        "\n"
        "Run pdftotext before attempting to parse any table.\n"
    )
    candidate = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=skill_md,
    )
    library = SkillLibrary(FakeSkillStorage([candidate]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-002
def test_ac_feat_001_002_no_part_of_a_skill_body_appears_anywhere_in_the_listing() -> None:
    """Discovery hands back metadata only; the instructions stay on the server.

    This is Progressive Disclosure, the reason the protocol has three operations
    instead of one: `list_skills` may cost the client a name and a description, and
    the Body is paid for only when that specific skill is asked for. A leak here is
    silent — the listing still looks correct — and it defeats the entire purpose of
    the server, so the assertion is deliberately uncompromising.

    The Body carries a sentinel that could not plausibly occur in a name or a
    description, placed in the middle of a multi-paragraph Body rather than on its
    first line: an implementation that leaked "the first line after the frontmatter"
    or "the first paragraph" would survive a one-line Body and must not survive this
    one. The sentinel's presence in the SKILL.md is asserted first, so a typo cannot
    quietly turn the test into one that proves nothing.

    The search covers the whole returned structure, not the two fields the summary is
    known to carry: see `_every_string_reachable_from`. And the skill is asserted
    *present* in the catalogue, because a sentinel is trivially absent from a listing
    that dropped the skill altogether — the test has to distinguish "did not leak"
    from "did not list".
    """
    sentinel = "XYZZY-PLUGH-DO-NOT-DISCLOSE-THE-BODY-7f3a91"
    body = (
        "# Processing PDF files\n"
        "\n"
        "Inspect the document structure before extracting anything from it.\n"
        "\n"
        "## Tables\n"
        "\n"
        f"Run pdftotext with the layout flag first. {sentinel} is an instruction\n"
        "that belongs to the Body and must never travel with a listing.\n"
        "\n"
        "## Fallback\n"
        "\n"
        "When the layout heuristic fails, crop the page and retry it on its own.\n"
    )
    skill_md = (
        "---\n"
        "name: pdf-processing\n"
        "description: Extracts text and tables from PDF files.\n"
        "---\n"
        "\n"
    ) + body
    assert sentinel in skill_md

    candidate = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=skill_md,
    )
    library = SkillLibrary(FakeSkillStorage([candidate]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    assert [summary.name.value for summary in summaries] == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."

    leaking = [text for text in _every_string_reachable_from(summaries) if sentinel in text]
    assert leaking == [], (
        "a Discovery response carried part of a skill's Body; "
        f"the Body sentinel {sentinel!r} was found in: {leaking!r}"
    )


# AC-FEAT-001-001
def test_ac_feat_001_001_three_valid_skills_are_listed_each_with_its_own_name_and_description() -> None:
    """A skills root holding three Valid Skills yields three summaries, correctly paired.

    This is the main path of Discovery, and the half of it that is easy to
    under-test is the pairing. Returning three entries, or returning the right
    three names, proves nothing on its own: an implementation that reads the names
    from one candidate and the descriptions from another satisfies both. So the
    three skills are made genuinely distinct — three different names and three
    different descriptions, none a substring or rearrangement of another — and each
    name is asserted against the description declared in its *own* SKILL.md. Any
    shuffle between the three fails.

    "Exactly" is the other word that carries weight. Each body says something the
    description does not, and each frontmatter declares optional fields the summary
    has no field for, so a description that swallowed a body, a fence line or an
    optional value would not equal the literal expected here.

    The three expected pairs are the literals written into the frontmatter above,
    read off the file rather than recomputed the way the code computes them.
    """
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "license: Apache-2.0\n"
            "---\n"
            "\n"
            "Run pdftotext before attempting to parse any table.\n"
        ),
    )
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=(
            "---\n"
            "name: commit-helper\n"
            "description: Writes conventional commit messages from a staged diff.\n"
            "allowed-tools: Read Grep\n"
            "---\n"
            "\n"
            "Read the staged diff before proposing any subject line.\n"
        ),
    )
    slide_deck = FakeSkillCandidate(
        directory_name="slide-deck",
        skill_md_text=(
            "---\n"
            "name: slide-deck\n"
            "description: Turns an outline into a presentation with speaker notes.\n"
            "metadata:\n"
            "  author: Example Org\n"
            "---\n"
            "\n"
            "One idea per slide; the notes carry everything else.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([pdf_processing, commit_helper, slide_deck]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    assert len(summaries) == 3
    assert sorted((summary.name.value, summary.description) for summary in summaries) == [
        ("commit-helper", "Writes conventional commit messages from a staged diff."),
        ("pdf-processing", "Extracts text and tables from PDF files."),
        ("slide-deck", "Turns an outline into a presentation with speaker notes."),
    ]


# AC-FEAT-001-003
def test_ac_feat_001_003_one_invalid_skill_between_two_valid_ones_costs_only_itself() -> None:
    """A single bad skill is dropped and the whole of the rest of the catalogue survives.

    The exclusion criteria pin *which* skills are invalid. This one pins the
    containment of the damage (BR-1): one offender among sound skills must not take
    the catalogue down with it, and the survivors must come back intact and complete.

    Position is what makes the test bite. The offender sits *between* the two valid
    skills in the order the storage yields them, so an implementation that stops at
    the first failure loses `commit-helper`, and one that abandons the remainder of
    the sequence loses it too. Either would pass a test where the offender is last.

    The assertion is on the whole result rather than on the offender's absence: the
    two survivors must both be there, nothing else may be, and each must carry the
    description declared in its *own* SKILL.md — the two are made genuinely distinct
    so a name read from one candidate and a description from another cannot pass.
    The order is the storage's, which the contract fixes for the return value.

    The offender's only flaw is the mismatch between its declared `name` and its
    directory, which is the criterion's wording; its description and its frontmatter
    are otherwise beyond reproach, so nothing else can be what excludes it.
    """
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "---\n"
            "\n"
            "Run pdftotext before attempting to parse any table.\n"
        ),
    )
    mismatched = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: other-name\n"
            "description: Declares a name that is not its directory's.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=(
            "---\n"
            "name: commit-helper\n"
            "description: Writes conventional commit messages from a staged diff.\n"
            "---\n"
            "\n"
            "Read the staged diff before proposing any subject line.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([pdf_processing, mismatched, commit_helper]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    assert [(summary.name.value, summary.description) for summary in summaries] == [
        ("pdf-processing", "Extracts text and tables from PDF files."),
        ("commit-helper", "Writes conventional commit messages from a staged diff."),
    ]


# AC-FEAT-001-020
def test_ac_feat_001_020_skill_whose_compatibility_exceeds_500_characters_is_excluded() -> None:
    """A `compatibility` longer than 500 characters keeps the skill out of the catalogue.

    `compatibility` is optional, but the Agent Skills specification caps it at 500
    characters when it is declared. The offender declares 501 and nothing else is
    wrong with it: its name is well-formed and equal to its directory's, and its
    description sits inside 1 to 1024 characters, so neither AC-016, AC-017 nor
    AC-018 can be what excludes it.

    The companion skill declares exactly 500 characters and must survive. That is
    what makes the test prove *where* the limit falls rather than merely that a
    long string is disliked: 500 in, 501 out. Per BR-1 the read still succeeds and
    drops the offender silently, so the escape of any exception is reported as a
    failure of this criterion rather than left to surface as an error.
    """
    longest_allowed_compatibility = "c" * 500
    one_character_too_long = "c" * 501

    offender = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: demo-skill\n"
            "description: Declares a compatibility one character over the cap.\n"
            f'compatibility: "{one_character_too_long}"\n'
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            f'compatibility: "{longest_allowed_compatibility}"\n'
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([offender, sound]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-036
@pytest.mark.parametrize(
    "compatibility_block",
    [
        pytest.param("compatibility: 42\n", id="number-not-a-string"),
        pytest.param("compatibility: true\n", id="boolean-not-a-string"),
    ],
)
def test_ac_feat_001_036_skill_whose_compatibility_is_not_a_string_is_excluded(
    compatibility_block: str,
) -> None:
    """A `compatibility` that YAML loads as a non-string value keeps the skill out.

    `compatibility` is optional, but when it is declared the Agent Skills
    specification requires it to be a string (1 to 500 characters). YAML happily
    loads an unquoted `42` as an integer and an unquoted `true` as a boolean rather
    than as the strings they look like, so an implementation that trusts the file's
    appearance rather than the parsed value would let both through. Nothing else is
    wrong with either offender: its name is well-formed and equal to its
    directory's, and its description sits inside 1 to 1024 characters, so neither
    AC-016, AC-017 nor AC-018 can be what excludes it. This is the same rule as
    AC-020 (a too-long string), applied to the wrong type instead of the wrong
    length.

    The companion skill declares the same value, quoted, so YAML loads it as the
    string it looks like, and it must survive. Per BR-1 the read still succeeds and
    drops the offender silently, so the escape of any exception is reported as a
    failure of this criterion rather than left to surface as an error.
    """
    offender = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=(
            "---\n"
            "name: demo-skill\n"
            "description: Declares a compatibility that is not a string.\n"
            f"{compatibility_block}"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            'compatibility: "stable"\n'
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([offender, sound]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."


# AC-FEAT-001-031
@pytest.mark.parametrize(
    "frontmatter_block",
    [
        pytest.param("description: Declares no name key at all.\n", id="valid-yaml-missing-name-key"),
        pytest.param("- first-item\n- second-item\n", id="valid-yaml-not-a-mapping-at-all"),
    ],
)
def test_ac_feat_001_031_frontmatter_missing_name_or_not_a_mapping_is_excluded_without_raising(
    frontmatter_block: str,
) -> None:
    """Syntactically valid YAML that is missing `name`, or is not a mapping, is dropped silently.

    Both cases load without error under any YAML parser: a mapping lacking the
    required `name` key, and a top-level value that is a sequence rather than a
    mapping at all. Neither is a YAML syntax failure (that is AC-019's territory);
    each is valid YAML whose *shape* the Agent Skills specification forbids. The
    contract fixes `list_skills` as never raising (BR-1), so the skill must simply
    be absent from the catalogue and the read must still complete.

    The sound skill offered alongside proves the drop is the offender's doing and
    not the whole catalogue read collapsing.
    """
    offender = FakeSkillCandidate(
        directory_name="demo-skill",
        skill_md_text=("---\n" f"{frontmatter_block}" "---\n" "\n" "Body text.\n"),
    )
    sound = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=(
            "---\n"
            "name: pdf-processing\n"
            "description: Extracts text and tables from PDF files.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    library = SkillLibrary(FakeSkillStorage([offender, sound]))

    try:
        summaries = library.list_skills()
    except Exception as exc:  # noqa: BLE001 - the contract fixes list_skills as never raising
        pytest.fail(
            "list_skills must never let an exception escape the catalogue read; "
            f"it raised {type(exc).__name__}: {exc}"
        )

    catalogued = [summary.name.value for summary in summaries]
    assert "demo-skill" not in catalogued
    assert catalogued == ["pdf-processing"]
    assert summaries[0].description == "Extracts text and tables from PDF files."
