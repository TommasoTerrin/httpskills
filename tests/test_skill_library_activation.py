"""Activation behaviour of the SkillLibrary seam, driven by a fake SkillStorage.

Discovery lives in `test_skill_library_listing.py`; the fake port and the fake
candidate are reused from there rather than duplicated, so both levels of
Progressive Disclosure are exercised through exactly the same substitute.
"""

import pytest
from test_skill_library_listing import FakeSkillCandidate, FakeSkillStorage

from httpskills.domain.errors import ResourceNotFound
from httpskills.domain.library import SkillLibrary
from httpskills.domain.model import ResolvedPair, ResolvedLocation

# A SKILL.md written the way an author writes one, not the way a serialiser
# would emit one. Every peculiarity below is legal YAML and legal Markdown, and
# every one of them is lost by an implementation that parses the frontmatter and
# dumps it back out:
#   - a comment line inside the frontmatter, which no YAML dumper preserves;
#   - `description` declared before `name`, an unusual but perfectly legal order
#     that a dumper re-sorts or re-groups;
#   - an optional field (`license`) between them, and two more after the nested
#     `metadata` block;
#   - run-together spacing (`author:   Example Org`) and a quoted `"1.4.0"` that
#     a dumper restyles into a single space and, respectively, into a bare or
#     single-quoted scalar;
#   - a `---` line of the skill's own inside the Body, which a splitter that
#     looks for the *last* fence, or that splits on every fence, mangles;
#   - two trailing spaces on the "Tables" line, a Markdown hard line break that
#     any reflow or strip silently eats.
SKILL_MD_PDF_PROCESSING = (
    "---\n"
    "# Authored by hand: the key order and this comment are part of the file.\n"
    "description: Extracts text and tables from PDF files.\n"
    "license: Apache-2.0\n"
    "name: pdf-processing\n"
    "metadata:\n"
    "  author:   Example Org\n"
    '  version: "1.4.0"\n'
    "compatibility: Requires poppler-utils 22 or newer.\n"
    "allowed-tools: Read Grep Glob\n"
    "---\n"
    "\n"
    "# Processing PDF files\n"
    "\n"
    "Inspect the document structure before extracting anything from it.  \n"
    "\n"
    "---\n"
    "\n"
    "## Tables\n"
    "\n"
    "Run pdftotext with the layout flag first.\n"
)

class FakeContainedSkillStorage(FakeSkillStorage):
    """Extends the Discovery fake with real `resolve`/`read_resource` behaviour.

    Discovery's `FakeSkillStorage` deliberately fails loudly on these two
    operations, because Discovery never reaches them. Resource retrieval does, so
    this substitute is kept separate rather than weakening the shared fake: a
    skill's resolved root is looked up by directory name, a relative path is split
    into segments and appended to it (mirroring what the real port's `resolve` is
    contracted to do), and `read_resource` looks the resulting location up in a
    small in-memory map of already-resolved locations to bytes.
    """

    def __init__(
        self,
        candidates: object,
        skill_roots: dict[str, tuple[str, ...]],
        files: dict[tuple[str, ...], bytes],
    ) -> None:
        super().__init__(candidates)  # type: ignore[arg-type]
        self._skill_roots = skill_roots
        self._files = files

    def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair:
        skill_root = self._skill_roots[directory_name]
        target = skill_root + tuple(relative_path.split("/"))
        return ResolvedPair(skill_root=skill_root, target=target)

    def read_resource(self, location: tuple[str, ...]) -> bytes:
        try:
            return self._files[location]
        except KeyError:
            raise ResourceNotFound(name="", path="/".join(location)) from None


SKILL_MD_COMMIT_HELPER = (
    "---\n"
    "name: commit-helper\n"
    "description: Writes conventional commit messages from a staged diff.\n"
    "---\n"
    "\n"
    "Read the staged diff before proposing any subject line.\n"
)


# AC-FEAT-001-005
def test_ac_feat_001_005_get_skill_returns_that_skill_s_skill_md_byte_for_byte() -> None:
    """Activation hands back the stored SKILL.md verbatim, frontmatter and body.

    This is the second level of Progressive Disclosure, and the word that carries
    the criterion is "byte-for-byte". The client is meant to receive the file the
    skill's author wrote, not a reconstruction of it: a round trip through a YAML
    dumper reorders keys, restyles quoting, drops comments and normalises spacing,
    and what comes back is then a different skill that merely means the same thing.
    The contract puts that verbatim text on `Skill.source_text` and deliberately
    gives `Skill` no parsed body, so the assertion is a single equality against the
    exact string the storage was given.

    The SKILL.md above is built to be hostile to any implementation that rebuilds
    rather than returns — see the comment on `SKILL_MD_PDF_PROCESSING` for what
    each peculiarity costs such an implementation. It remains a Valid Skill
    throughout: a well-formed `name` equal to its directory's, a description
    inside 1 to 1024 characters, and optional fields all within their limits.

    Two skills are offered to the storage, and the one asked for is yielded
    *second*. An implementation that returns whatever candidate comes first, or
    that ignores the requested name entirely, cannot survive that.

    The expected value is the literal above, which is the file as stored — the
    independent source the criterion names. Nothing here is recomputed by parsing
    and re-emitting it, which would be the tautology this criterion exists to
    forbid. The peculiarities are pinned with their own assertions first, so a
    typo in the literal cannot quietly turn this into a test of a bland file.
    """
    assert "# Authored by hand" in SKILL_MD_PDF_PROCESSING, "the YAML comment must be present"
    assert (
        SKILL_MD_PDF_PROCESSING.index("description:") < SKILL_MD_PDF_PROCESSING.index("name:")
    ), "description must be declared before name"
    assert "  author:   Example Org\n" in SKILL_MD_PDF_PROCESSING, "the wide spacing must be present"
    assert '  version: "1.4.0"\n' in SKILL_MD_PDF_PROCESSING, "the quoted version must be present"
    assert "it.  \n" in SKILL_MD_PDF_PROCESSING, "the hard-break trailing spaces must be present"
    assert "\n\n---\n\n## Tables\n" in SKILL_MD_PDF_PROCESSING, "the body's own rule must be present"

    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper, pdf_processing]))

    skill = library.get_skill("pdf-processing")

    assert skill.source_text == SKILL_MD_PDF_PROCESSING
    assert skill.frontmatter.name.value == "pdf-processing"


# AC-FEAT-001-006
def test_ac_feat_001_006_undefined_frontmatter_key_leaves_the_skill_valid_and_comes_back_unchanged() -> None:
    """A frontmatter key the specification does not define is kept, not rejected and not dropped.

    The Agent Skills specification defines six keys; it does not forbid a seventh.
    An author who annotates a skill for their own tooling must not thereby make it
    invalid, and the client must receive what the author wrote. So the criterion has
    two halves, and both are asserted here, because either alone is satisfiable by a
    wrong implementation: a validator that rejects unknown keys fails the first, and
    a `get_skill` that re-serialises the frontmatter it parsed fails the second while
    passing the first.

    Validity is observed through the seam rather than through a validation flag: an
    excluded skill is `SkillNotFound` (BR-1 makes an invalid skill indistinguishable
    from an absent one), so a `Skill` coming back at all *is* the first half. The
    exception is caught and reported explicitly so a rejection reads as this
    criterion failing rather than as a suite error.

    "Unchanged" is asserted against the stored literal, which is the independent
    source: `source_text` must equal the file the storage was given, byte for byte.
    The two undefined keys are written the way a hand-authored file writes them and
    not the way a dumper would emit them — run-together spacing on one, a quoted
    scalar that YAML would restyle bare on the other, and both declared *between*
    keys the specification does define, a position no re-emission preserves.

    The contract gives `SkillFrontmatter.undefined_keys` the parsed half of the same
    promise, so the mapping is pinned by equality rather than by presence: exactly
    the two undefined keys, with exactly the values the frontmatter declared. An
    implementation that swept the whole frontmatter in there — name, description and
    license along with the rest — would pass any containment check and fails this
    one, and that is the point of asserting equality.
    """
    undefined_owner_line = "x-internal-owner:   platform-team\n"
    undefined_review_line = 'x-review-cycle: "2026-Q3"\n'
    skill_md = (
        "---\n"
        "name: pdf-processing\n"
        f"{undefined_owner_line}"
        "description: Extracts text and tables from PDF files.\n"
        f"{undefined_review_line}"
        "license: Apache-2.0\n"
        "---\n"
        "\n"
        "# Processing PDF files\n"
        "\n"
        "Run pdftotext with the layout flag before parsing any table.\n"
    )
    assert undefined_owner_line in skill_md, "the wide-spaced undefined key must be present"
    assert undefined_review_line in skill_md, "the quoted undefined key must be present"

    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=skill_md,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper, pdf_processing]))

    try:
        skill = library.get_skill("pdf-processing")
    except Exception as exc:  # noqa: BLE001 - a key the spec does not define must not invalidate
        pytest.fail(
            "a frontmatter key the specification does not define must leave the skill "
            f"valid; get_skill raised {type(exc).__name__}: {exc}"
        )

    assert skill.source_text == skill_md
    assert undefined_owner_line in skill.source_text
    assert undefined_review_line in skill.source_text
    assert skill.frontmatter.name.value == "pdf-processing"
    assert skill.frontmatter.description == "Extracts text and tables from PDF files."
    assert dict(skill.frontmatter.undefined_keys) == {
        "x-internal-owner": "platform-team",
        "x-review-cycle": "2026-Q3",
    }


# AC-FEAT-001-007
def test_ac_feat_001_007_activating_a_name_no_directory_carries_raises_skill_not_found() -> None:
    """Asking for a skill the library does not hold raises ERR-001, carrying the name asked for.

    The contract fixes exceptions as the return convention for the whole of this
    feature, so a miss is a raise and never a sentinel, a `None` or an empty
    `Skill`. ERR-001 is `SkillNotFound`, and the error table gives it one field,
    `name`, which must carry the name the client asked for — an error that merely
    says "not found" leaves the transport nothing to tell the client it asked for.

    The storage is not empty. It holds `commit-helper`, a Valid Skill in every
    respect, so what this test observes is a *lookup that missed* and not a
    catalogue that had nothing to offer: an implementation that raises whenever the
    first candidate is not the one wanted, or that never looks past an empty
    result, is not what the criterion asks for.

    The error type is pinned by identity rather than by import. The contract names
    `SkillNotFound` and its base `SkillLibraryError` but does not fix the module
    they live in, and the layout of the domain's modules is the implementer's to
    choose; a hard import here would freeze a decision the contract left open. So
    the raised exception is required to be exactly `SkillNotFound` — not a base
    class, not a builtin, not a `NotImplementedError` standing in for unwritten
    code — declared inside this package and descending from `SkillLibraryError`.
    """
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_skill("absent-skill")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "get_skill must signal an absent skill with ERR-001 (SkillNotFound); "
        f"it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "absent-skill", (
        "SkillNotFound carries a `name` field holding the name that was asked for; "
        f"it held {getattr(raised, 'name', None)!r}"
    )


# AC-FEAT-001-008
def test_ac_feat_001_008_activating_a_directory_that_fails_validation_raises_skill_not_found_indistinguishably() -> None:
    """Asking for a skill whose directory exists but fails validation raises ERR-001, exactly as an absent skill does.

    BR-1 says an invalid skill must be indistinguishable from one that is not
    there at all, and this criterion is that rule applied to Activation rather
    than to Discovery: the directory is real, the storage yields it, but the
    declared `name` in its frontmatter does not match its directory's, so it is
    not a Valid Skill (the same rule AC-016 exercises on the listing side). The
    contract's error table gives this exact case its own row: the candidate
    exists but is not a Valid Skill, and the outcome is ERR-001 with no field
    or detail that would let a caller tell it apart from a directory that was
    never there.

    A sound skill is offered alongside so the raise is the invalid candidate's
    doing and not an empty storage. The error is asserted the same way AC-007
    asserts it — by exact type name, module and ancestry, and by the `name`
    field carrying precisely the directory name that was asked for — because
    that field is the only thing ERR-001 carries, and it must not leak the
    validation failure (no `reason`, no distinguishing detail) alongside it.
    """
    invalid = FakeSkillCandidate(
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
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    library = SkillLibrary(FakeSkillStorage([invalid, sound]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_skill("demo-skill")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "get_skill must signal a directory that fails validation with ERR-001 "
        f"(SkillNotFound), the same error as an absent skill; it raised "
        f"{raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "demo-skill", (
        "SkillNotFound carries a `name` field holding the name that was asked for, "
        "and nothing that distinguishes an invalid skill from an absent one; "
        f"it held {getattr(raised, 'name', None)!r}"
    )


# AC-FEAT-001-037
def test_ac_feat_001_037_get_resource_for_a_directory_that_fails_validation_raises_skill_not_found() -> None:
    """Asking `get_resource` for a directory that exists but fails validation raises ERR-001, the same error `get_skill` raises for the identical directory (AC-008).

    AC-008 proves this exact "exists but is not a Valid Skill" case for
    `get_skill`; the error table's `SkillNotFound` row covers the identical
    condition regardless of which of the three operations asks for it: "the
    candidate exists but is not a Valid Skill". This test is that same
    directory, offered to `get_resource` instead — a directory whose
    frontmatter declares a `name` different from its own, exactly as AC-008
    builds it.

    The plain Discovery `FakeSkillStorage` is used, not
    `FakeContainedSkillStorage`: its `resolve` and `read_resource` both raise
    `AssertionError` unconditionally if called at all, so an implementation
    that tried to resolve the path before validating the candidate would
    surface that `AssertionError` here instead of `SkillNotFound` — the path
    itself never needs to resolve to anything real, because `SkillNotFound`
    must fire before any path resolution is attempted.

    A sound skill is offered alongside so the raise is the invalid
    candidate's doing and not an empty storage. The error is asserted the
    same way AC-007, AC-008 and AC-015 assert it — by exact type name, module
    and ancestry, and by the `name` field carrying precisely the directory
    name that was asked for, with no field or detail (no `reason`, nothing
    path-related) that would let a caller tell it apart from an absent
    directory — and specifically not `InvalidSkill`, not `InvalidSkillName`,
    and not `ResourceNotFound`.
    """
    invalid = FakeSkillCandidate(
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
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    library = SkillLibrary(FakeSkillStorage([invalid, sound]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error (including the fake's own AssertionError, if a port method for
    # path resolution was reached) is reported as this criterion failing
    # rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("demo-skill", "references/whatever.md")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "get_resource must signal a directory that fails validation with "
        "ERR-001 (SkillNotFound), the same error get_skill raises for the "
        f"identical directory (AC-008); it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "demo-skill", (
        "SkillNotFound carries a `name` field holding the name that was asked "
        "for, and nothing that distinguishes an invalid skill from an absent "
        f"one; it held {getattr(raised, 'name', None)!r}"
    )


# AC-FEAT-001-009
def test_ac_feat_001_009_get_resource_returns_the_named_resource_s_content() -> None:
    """Retrieving a resource bundled with a valid skill returns that file's bytes.

    This is the third level of Progressive Disclosure: a reference file the Body
    points to, fetched only when the client asks for it by its path relative to
    the skill's own directory. The seam is asked for `references/REFERENCE.md`
    and the storage is wired so that path resolves, through `resolve`, to a
    location holding a known byte string — the independent source named by the
    criterion, not a value recomputed the way `get_resource` would compute it.

    `resolve` and `read_resource` are exercised for real here, through a fake
    built for this purpose, rather than through the Discovery fake's stubs that
    refuse to be called at all. `resolve` returns the two locations as segment
    tuples per the contract, and `read_resource` reads the resolved target — the
    domain is expected to ask for a location strictly inside the skill's own
    root, but that containment check is a separate criterion; this one is the
    plain successful retrieval the others build on.
    """
    reference_content = b"# Reference\n\nCanonical field names for the PDF schema.\n"
    skill_root = ("skills", "pdf-processing")
    reference_location = (*skill_root, "references", "REFERENCE.md")

    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = FakeContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={reference_location: reference_content},
    )
    library = SkillLibrary(storage)

    content = library.get_resource("pdf-processing", "references/REFERENCE.md")

    assert content == reference_content


# AC-FEAT-001-010
def test_ac_feat_001_010_get_resource_returns_an_asset_file_s_content() -> None:
    """Retrieving a file bundled under a skill's `assets/` directory returns that file's bytes.

    AC-009 proves Progressive Disclosure's third level for `references/`; this is
    the same proof for `assets/`, the specification's other resource directory.
    The seam is asked for `assets/template.txt` and the storage is wired so that
    path resolves, through `resolve`, to a location holding a known byte string —
    the independent source named by the criterion, not a value recomputed the way
    `get_resource` would compute it.

    `resolve` and `read_resource` are exercised for real here, through the same
    fake AC-009 uses, rather than through the Discovery fake's stubs that refuse
    to be called at all.
    """
    template_content = b"Subject: {{subject}}\n\nBody:\n{{body}}\n"
    skill_root = ("skills", "pdf-processing")
    template_location = (*skill_root, "assets", "template.txt")

    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = FakeContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={template_location: template_content},
    )
    library = SkillLibrary(storage)

    content = library.get_resource("pdf-processing", "assets/template.txt")

    assert content == template_content


# AC-FEAT-001-011
def test_ac_feat_001_011_get_resource_for_a_path_that_resolves_inside_the_skill_but_does_not_exist_raises_resource_not_found() -> None:
    """A path that resolves inside a valid skill's own directory, but names no file there, raises ERR-002.

    This is Progressive Disclosure's third level failing the way AC-009 and
    AC-010 succeed: the requested path — `references/missing.md` — is
    unambiguously inside `pdf-processing`'s own root, so containment is not in
    question here (that is AC-012's concern); nothing is readable at the
    resolved location. The error table gives this exact case its own row,
    distinct from `ResourceNotContained`: the resolved location is inside the
    skill, but absent, or a directory.

    The storage is wired, through the same `FakeContainedSkillStorage` AC-009
    and AC-010 use, so that `resolve("pdf-processing", "references/missing.md")`
    lands on a location that is simply not present in the fake's in-memory file
    map — nothing stubs the miss directly, it falls out of asking for a path
    that was never populated.

    The error type is pinned by identity rather than by import, exactly as
    AC-007 and AC-008 pin `SkillNotFound`: the contract names `ResourceNotFound`
    and its base `SkillLibraryError` but does not fix the module it lives in, so
    a hard import of the concrete exception would freeze a decision the
    contract left open. The raised exception is required to be exactly
    `ResourceNotFound` — not a `KeyError`, not a builtin, not a stand-in for
    unwritten code — declared inside this package and descending from
    `SkillLibraryError`.
    """
    skill_root = ("skills", "pdf-processing")
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = FakeContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={},
    )
    library = SkillLibrary(storage)

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("pdf-processing", "references/missing.md")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotFound", (
        "get_resource must signal a resolved-but-absent resource with ERR-002 "
        f"(ResourceNotFound); it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotFound must be this feature's own error type, not a builtin "
        f"or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotFound's ancestry was {sorted(ancestry)}"
    )


# AC-FEAT-001-012
def test_ac_feat_001_012_get_resource_with_an_absolute_path_raises_resource_not_contained_without_reading_a_file() -> None:
    """An absolute `path` argument to `get_resource` raises ERR-003, and no file is read to get there.

    `ResourcePath.__post_init__` rejects a value that is empty or absolute before
    any resolution happens, and the contract's "What is NOT frozen" section fixes
    the ordering explicitly for this exact criterion: "a path that is absolute is
    rejected before any resolution (AC-012 says no file is read)". So this is not
    only a check of which error comes back, but of when it is raised relative to
    the storage port.

    The skill asked for is a Valid Skill — `pdf-processing`, built from the same
    literal AC-009 through AC-011 use — so a wrong implementation cannot dodge the
    assertion by raising `SkillNotFound` for an unrelated reason; the only thing
    that can make this path fail is the absoluteness of the path itself.

    "No file is read" is exercised through the plain `FakeSkillStorage` from
    Discovery, not `FakeContainedSkillStorage`: its `resolve` and `read_resource`
    both raise `AssertionError` unconditionally if called at all (see its
    docstring: "the other two operations fail loudly so an accidental call is
    visible"). An implementation that calls either port method before validating
    the path is absolute would surface that `AssertionError` here, not
    `ResourceNotContained` — proving the ordering, not just the outcome.

    The error type is pinned by identity rather than by import, exactly as AC-007,
    AC-008 and AC-011 pin their errors: the contract names `ResourceNotContained`
    and its base `SkillLibraryError` but does not fix the module it lives in.
    """
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    library = SkillLibrary(FakeSkillStorage([pdf_processing]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error (including the fake's own AssertionError, if a port method was
    # reached) is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("pdf-processing", "/etc/passwd")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotContained", (
        "get_resource must signal an absolute path with ERR-003 "
        "(ResourceNotContained), rejecting it before any resolution is attempted; "
        f"it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotContained must be this feature's own error type, not a "
        f"builtin or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotContained's ancestry was {sorted(ancestry)}"
    )


# AC-FEAT-001-032
def test_ac_feat_001_032_get_resource_with_an_empty_path_raises_resource_not_contained_without_reading_a_file() -> None:
    """An empty-string `path` argument to `get_resource` raises ERR-003, and no file is read to get there.

    The contract's data types section is explicit that `ResourcePath.__post_init__`
    rejects a value unless it "is non-empty", listed as a distinct rule from "is
    not an absolute path", and the error table's `ResourceNotContained` row names
    both conditions in the same breath: "the path is absolute or empty". So an
    empty string is not merely a degenerate case of AC-012's absolute path; it is
    the contract's other named rejection, and it must be rejected before any
    resolution happens, exactly as AC-012 requires for an absolute path.

    The skill asked for is a Valid Skill — `pdf-processing`, built from the same
    literal AC-009 through AC-012 use — so a wrong implementation cannot dodge the
    assertion by raising `SkillNotFound` for an unrelated reason; the only thing
    that can make this path fail is the emptiness of the path itself.

    "No file is read" is exercised through the plain `FakeSkillStorage` from
    Discovery, not `FakeContainedSkillStorage`: its `resolve` and `read_resource`
    both raise `AssertionError` unconditionally if called at all (see its
    docstring: "the other two operations fail loudly so an accidental call is
    visible"). An implementation that calls either port method before validating
    the path is empty would surface that `AssertionError` here, not
    `ResourceNotContained` — proving the ordering, not just the outcome.

    The error type is pinned by identity rather than by import, exactly as
    AC-007, AC-008, AC-011 and AC-012 pin their errors: the contract names
    `ResourceNotContained` and its base `SkillLibraryError` but does not fix the
    module it lives in.
    """
    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    library = SkillLibrary(FakeSkillStorage([pdf_processing]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error (including the fake's own AssertionError, if a port method was
    # reached) is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("pdf-processing", "")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotContained", (
        "get_resource must signal an empty path with ERR-003 "
        "(ResourceNotContained), rejecting it before any resolution is attempted; "
        f"it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotContained must be this feature's own error type, not a "
        f"builtin or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotContained's ancestry was {sorted(ancestry)}"
    )


class _SymlinkEscapingContainedSkillStorage(FakeContainedSkillStorage):
    """Resolves a specific relative path the way a real filesystem port would
    resolve a symlink: the requested path stays inside the skill directory in
    its *literal* form, but `resolve` follows the symlink to wherever it
    actually points, which here is a location sharing none of `skill_root`'s
    prefix. `FakeContainedSkillStorage.resolve` derives `target` purely by
    appending `relative_path`'s own segments to `skill_root`, which can never
    model a symlink — the whole point of a symlink is that its resolved
    target is independent of where the link itself sits. This override maps
    one specific relative path straight to an outside target, the way
    `resolve` is contracted to (ADR-0002 step 2: it follows the path to its
    real location, symlinks included, before the domain ever compares it).
    """

    def __init__(
        self,
        candidates: object,
        skill_roots: dict[str, tuple[str, ...]],
        files: dict[tuple[str, ...], bytes],
        symlink_targets: dict[str, ResolvedLocation],
    ) -> None:
        super().__init__(candidates, skill_roots, files)  # type: ignore[arg-type]
        self._symlink_targets = symlink_targets

    def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair:
        skill_root = self._skill_roots[directory_name]
        if relative_path in self._symlink_targets:
            return ResolvedPair(
                skill_root=skill_root,
                target=self._symlink_targets[relative_path],
            )
        return super().resolve(directory_name, relative_path)


# AC-FEAT-001-014
def test_ac_feat_001_014_get_resource_for_a_symlink_whose_target_lies_outside_the_skill_raises_resource_not_contained() -> None:
    """A `path` that names a symlink inside the skill, but whose target resolves outside the skill's own root, raises ERR-003, and the target's content is not returned.

    AC-012 and AC-013 prove ERR-003 for a path rejected before resolution and
    for one that escapes via literal `..` segments; this is the error table's
    same `ResourceNotContained` row from its third angle: a path that is
    itself a perfectly ordinary, non-absolute, contained-looking name —
    `linked-config` — but is a symlink whose real target, once `resolve`
    follows it (ADR-0002 step 2), lands on `("etc", "secrets", "prod.yaml")`,
    a location sharing none of `skill_root`'s `("skills", "pdf-processing")`
    prefix. Nothing about the requested path string reveals the escape; only
    following the link does, which is exactly why containment is judged on
    `resolve`'s returned locations rather than on the path text.

    The outside location is wired, in the fake's in-memory file map, to hold
    a byte string that is not the skill's own — the independent source the
    criterion's second half names. If containment were not enforced,
    `get_resource` would hand that content back; the criterion demands it
    never does, so the test asserts the raise and, had no exception been
    raised, would have failed the content comparison too.

    The error type is pinned by identity rather than by import, exactly as
    AC-007, AC-008, AC-011, AC-012 and AC-013 pin theirs: the contract names
    `ResourceNotContained` and its base `SkillLibraryError` but does not fix
    the module it lives in.
    """
    outside_secret = b"admin_password: hunter2\n"
    skill_root = ("skills", "pdf-processing")
    outside_location: ResolvedLocation = ("etc", "secrets", "prod.yaml")

    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = _SymlinkEscapingContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={outside_location: outside_secret},
        symlink_targets={"linked-config": outside_location},
    )
    library = SkillLibrary(storage)

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        content = library.get_resource("pdf-processing", "linked-config")
        assert content != outside_secret, (
            "get_resource must not hand back a symlink's outside target, even "
            "if containment is not enforced with a raise"
        )

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotContained", (
        "get_resource must signal a symlink whose target lies outside the "
        "skill's own directory with ERR-003 (ResourceNotContained); "
        f"it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotContained must be this feature's own error type, not a "
        f"builtin or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotContained's ancestry was {sorted(ancestry)}"
    )


class _EscapingContainedSkillStorage(FakeContainedSkillStorage):
    """Resolves `..` segments the way a real filesystem port would: they walk
    back up out of the skill's own root rather than staying as literal path
    components. `FakeContainedSkillStorage.resolve` concatenates segments
    verbatim, which is faithful for AC-009 through AC-012 but would let a `..`
    segment survive into `target` unresolved — masking exactly the escape this
    criterion is about. This override collapses `..` the way the real
    `resolve` is contracted to (ADR-0002 step 2: it follows the path to its
    real location before the domain ever compares it), so `target` can
    legitimately land outside `skill_root`.
    """

    def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair:
        skill_root = self._skill_roots[directory_name]
        segments = list(skill_root)
        for part in relative_path.split("/"):
            if part == "..":
                segments.pop()
            elif part in ("", "."):
                continue
            else:
                segments.append(part)
        return ResolvedPair(skill_root=skill_root, target=tuple(segments))


# AC-FEAT-001-013
def test_ac_feat_001_013_get_resource_for_a_path_escaping_via_dot_dot_raises_resource_not_contained() -> None:
    """A `path` that resolves, through `..` segments, to a location outside the skill's own root raises ERR-003, and the outside file's content is not returned.

    AC-012 proves ERR-003 for a path that is rejected before any resolution;
    this is the other half the error table's `ResourceNotContained` row names:
    "its resolved location lies outside the skill's own resolved root". The
    path handed to `get_resource` — `../secrets/token.txt` — is not absolute
    and not empty, so `ResourcePath.__post_init__` accepts it, and only
    resolution reveals the escape: `resolve` walks one segment above
    `skill_root` before descending into `secrets/token.txt`, landing on
    `("skills", "secrets", "token.txt")`, which does not share `skill_root`'s
    `("skills", "pdf-processing")` prefix.

    The outside location is wired, in the fake's in-memory file map, to hold a
    byte string that is not the skill's own — the independent source the
    criterion's second half names. If containment were not enforced,
    `get_resource` would hand that content back; the criterion demands it
    never does, so the test asserts the raise and, had no exception been
    raised, would have failed the content comparison too.

    The error type is pinned by identity rather than by import, exactly as
    AC-007, AC-008, AC-011 and AC-012 pin theirs: the contract names
    `ResourceNotContained` and its base `SkillLibraryError` but does not fix
    the module it lives in.
    """
    outside_secret = b"TOP SECRET: do not disclose\n"
    skill_root = ("skills", "pdf-processing")
    outside_location: ResolvedLocation = ("skills", "secrets", "token.txt")

    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = _EscapingContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={outside_location: outside_secret},
    )
    library = SkillLibrary(storage)

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        content = library.get_resource("pdf-processing", "../secrets/token.txt")
        assert content != outside_secret, (
            "get_resource must not hand back a file outside the skill's own "
            "directory, even if containment is not enforced with a raise"
        )

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotContained", (
        "get_resource must signal a path that escapes the skill's own "
        "directory via '..' with ERR-003 (ResourceNotContained); "
        f"it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotContained must be this feature's own error type, not a "
        f"builtin or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotContained's ancestry was {sorted(ancestry)}"
    )


# AC-FEAT-001-029
def test_ac_feat_001_029_resolved_location_in_a_sibling_directory_whose_name_extends_the_skill_s_raises_resource_not_contained() -> None:
    """A resolved location inside a sibling directory whose name merely extends the skill's own raises ERR-003, even though that sibling's name is a string-prefix match.

    The contract is explicit about why this is a distinct case from AC-013 and
    AC-014: "A resolved location is a tuple of path segments, never a string.
    This is what makes AC-029 hard to get wrong: comparing `("skills",
    "demo-evil")` against `("skills", "demo")` cannot accidentally succeed the
    way a string prefix test does." The skill under test is `demo`, at resolved
    root `("skills", "demo")`; the resolved target lands in `("skills",
    "demo-evil", "secret.txt")` — a directory that sits right next to `demo`,
    sharing its parent, and whose name literally starts with `demo`, so a
    containment check written as `str(target).startswith(str(skill_root))` (or
    the path-string equivalent) would wrongly call this contained. Comparing
    whole path segments cannot: `"demo-evil" != "demo"` at the very first
    segment where the two tuples diverge.

    The path asked for — `sibling-file` — is not absolute and not empty, and it
    is not `..`-laden either, so `ResourcePath.__post_init__` accepts it and
    only `resolve` reveals where it actually lands, exactly as a symlink or a
    resolved indirection would in the real port (ADR-0002 step 2). The fake used
    here is the same symlink-style substitute AC-014 uses, which maps one
    specific relative path straight to an arbitrary resolved location, because
    that is precisely the shape of "the requested path looks fine; only
    resolution shows the escape."

    The outside location is wired to hold a byte string that is not `demo`'s
    own — the independent source the criterion's second half implies. If
    containment were judged by string prefix instead of by segment, that content
    would come back; the test asserts the raise, and had none been raised, the
    content comparison below would have failed too.

    The error type is pinned by identity rather than by import, exactly as
    AC-012, AC-013 and AC-014 pin theirs: the contract names
    `ResourceNotContained` and its base `SkillLibraryError` but does not fix the
    module it lives in.
    """
    sibling_secret = b"do-not-serve-this-its-a-different-skill\n"
    skill_root = ("skills", "demo")
    sibling_location: ResolvedLocation = ("skills", "demo-evil", "secret.txt")

    demo = FakeSkillCandidate(
        directory_name="demo",
        skill_md_text=(
            "---\n"
            "name: demo\n"
            "description: A minimal valid skill used to prove segment-wise containment.\n"
            "---\n"
            "\n"
            "Body text.\n"
        ),
    )
    storage = _SymlinkEscapingContainedSkillStorage(
        [demo],
        skill_roots={"demo": skill_root},
        files={sibling_location: sibling_secret},
        symlink_targets={"sibling-file": sibling_location},
    )
    library = SkillLibrary(storage)

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error is reported as this criterion failing rather than as a suite error.
    with pytest.raises(Exception) as caught:
        content = library.get_resource("demo", "sibling-file")
        assert content != sibling_secret, (
            "get_resource must not hand back a sibling directory's content just "
            "because its name extends the skill's own"
        )

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "ResourceNotContained", (
        "get_resource must signal a resolved location in a sibling directory "
        "whose name extends the skill's own with ERR-003 "
        f"(ResourceNotContained); it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "ResourceNotContained must be this feature's own error type, not a "
        f"builtin or a third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"ResourceNotContained's ancestry was {sorted(ancestry)}"
    )


# AC-FEAT-001-015
def test_ac_feat_001_015_get_resource_for_a_name_no_directory_carries_raises_skill_not_found() -> None:
    """Asking `get_resource` for a resource of a skill that does not exist raises ERR-001, not ERR-002 or ERR-003.

    This is AC-007's failure mode, proven on `get_resource` rather than on
    `get_skill`: the error table's `SkillNotFound` row covers "no candidate
    directory carries this name" regardless of which of the three operations
    asks. ERR-002 (`ResourceNotFound`) and ERR-003 (`ResourceNotContained`)
    are both about a path once a skill has been located; neither is reachable
    here, because the skill itself is never found, and the contract is explicit
    that the two are "indistinguishable, no detail that separates them" from an
    absent skill.

    The storage is not empty. It holds `commit-helper`, a Valid Skill, so what
    this test observes is a lookup that missed — not a catalogue with nothing to
    offer. The plain Discovery `FakeSkillStorage` is used rather than
    `FakeContainedSkillStorage`: its `resolve` and `read_resource` both raise
    `AssertionError` unconditionally if called at all, so an implementation that
    tried to resolve a path before confirming the skill exists would surface
    that `AssertionError` here instead of `SkillNotFound` — proving the miss is
    caught before any port call for the path, not just that some error comes
    back.

    The error type is pinned by identity rather than by import, exactly as
    AC-007 and AC-008 pin it: the contract names `SkillNotFound` and its base
    `SkillLibraryError` but does not fix the module it lives in, so a hard
    import of the concrete exception would freeze a decision the contract left
    open. The `name` field is asserted to carry precisely the name asked for,
    the only detail ERR-001 carries.
    """
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error (including the fake's own AssertionError, if a port method for
    # path resolution was reached) is reported as this criterion failing
    # rather than as a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("absent-skill", "references/any.md")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "get_resource must signal an absent skill with ERR-001 (SkillNotFound), "
        f"not a path-related error; it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "absent-skill", (
        "SkillNotFound carries a `name` field holding the name that was asked for; "
        f"it held {getattr(raised, 'name', None)!r}"
    )


# AC-FEAT-001-038
def test_ac_feat_001_038_get_resource_for_an_absent_skill_and_an_absolute_path_raises_skill_not_found_not_resource_not_contained() -> None:
    """Asking `get_resource` for a skill that does not exist, with a path that is also absolute, raises ERR-001, not ERR-003.

    AC-015 proves an absent skill wins over a *valid* path; AC-012 proves an
    absolute path is rejected for a skill that *does* exist. This criterion is
    the combination the "What is NOT frozen" section pins explicitly: "an
    unknown skill name is reported (`SkillNotFound`) before its path is
    validated at all, even when the path is also absolute or empty (AC-038) —
    `get_resource` checks skill existence first, path validity second." Both
    faults are present at once, and only skill-existence is allowed to win.

    The storage holds `commit-helper`, a Valid Skill, so the raise is a genuine
    lookup miss and not an empty catalogue. The plain Discovery `FakeSkillStorage`
    is used, not `FakeContainedSkillStorage`: its `resolve` and `read_resource`
    both raise `AssertionError` unconditionally if called at all, so an
    implementation that validated the path before checking the skill's existence
    would surface that `AssertionError`, or `ResourceNotContained`, here instead
    of `SkillNotFound`.

    The error type is pinned by identity rather than by import, exactly as
    AC-007, AC-008 and AC-015 pin `SkillNotFound`.
    """
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper]))

    # Caught broadly on purpose: the exact type is asserted below, so a wrong
    # error (including the fake's own AssertionError, if a port method for
    # path resolution was reached, or ResourceNotContained if path validity
    # was checked first) is reported as this criterion failing rather than as
    # a suite error.
    with pytest.raises(Exception) as caught:
        library.get_resource("absent-skill", "/etc/passwd")

    raised = caught.value
    raised_type = type(raised)
    ancestry = {ancestor.__name__ for ancestor in raised_type.__mro__}

    assert raised_type.__name__ == "SkillNotFound", (
        "get_resource must signal an absent skill with ERR-001 (SkillNotFound) "
        "even when the path is also invalid (absolute), not ERR-003 "
        f"(ResourceNotContained); it raised {raised_type.__name__}: {raised}"
    )
    assert raised_type.__module__.startswith("httpskills."), (
        "SkillNotFound must be this feature's own error type, not a builtin or a "
        f"third-party one; it was declared in {raised_type.__module__}"
    )
    assert "SkillLibraryError" in ancestry, (
        "every error of this contract derives from SkillLibraryError; "
        f"SkillNotFound's ancestry was {sorted(ancestry)}"
    )
    assert getattr(raised, "name", None) == "absent-skill", (
        "SkillNotFound carries a `name` field holding the name that was asked for; "
        f"it held {getattr(raised, 'name', None)!r}"
    )


# AC-FEAT-001-034
def test_ac_feat_001_034_skill_declaring_only_the_required_fields_returns_none_for_optionals_and_an_empty_metadata_mapping() -> None:
    """A skill declaring only `name` and `description` gets `None` back for every optional scalar field, and an empty mapping for `metadata` — not a placeholder.

    The contract's data types section fixes what an absent optional field becomes
    once parsed: `license: str | None # None when absent`, `compatibility: str |
    None`, `allowed_tools: str | None`, and `metadata: Mapping[str, str] # empty
    mapping when absent`. Three of the four optional fields collapse to the same
    sentinel, `None`, and the fourth deliberately does not — an implementation that
    reused `None` for `metadata` too, or that returned `{}`-like defaults for the
    scalar fields, would satisfy a laxer assertion than this one but not the
    contract's explicit distinction between "no value" and "no entries".

    `commit-helper`, the frontmatter this test uses, declares nothing beyond the
    two required keys, so this is the mirror image of AC-022 (which proves such a
    skill is catalogued at all): AC-022 is exercised through Discovery and
    `SkillSummary`, which has no field for any of the four; only `get_skill`, via
    `Skill.frontmatter`, can be asked what they actually came back as.

    The expected values are the literals the contract's data-types comment gives —
    `None`, `None`, `None`, and an empty mapping — not values recomputed the way
    `get_skill`'s own parsing would compute them.
    """
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper]))

    skill = library.get_skill("commit-helper")

    assert skill.frontmatter.license is None
    assert skill.frontmatter.compatibility is None
    assert skill.frontmatter.allowed_tools is None
    assert dict(skill.frontmatter.metadata) == {}


# AC-FEAT-001-030
def test_ac_feat_001_030_get_skill_returns_the_declared_values_of_license_compatibility_metadata_and_allowed_tools() -> None:
    """A skill declaring well-formed `license`, `compatibility`, `metadata` and `allowed-tools` gets each field back holding what was declared, not a placeholder.

    AC-023 proves these four optional fields keep a skill valid when they are
    well-formed; this criterion is about Activation rather than Discovery, and
    about the values themselves rather than mere validity. `SkillSummary` (what
    Discovery returns) has no field for any of the four, so only `get_skill`, via
    `Skill.frontmatter`, can be asked. The frontmatter carries `license` and
    `compatibility` as plain strings, `metadata` as a string-to-string mapping and
    `allowed_tools` as the space-separated string verbatim, per the contract's
    data types.

    The four values declared in the SKILL.md below are distinct from one another
    and from every other literal used elsewhere in this file, so a field reading
    from the wrong place in the frontmatter, or a placeholder/default value
    substituted for what was actually declared, cannot pass by accident. The
    expected values are exactly the literals written into the file, read off it
    rather than recomputed the way `get_skill` would compute them.

    A second, unrelated skill is offered alongside so a wrong implementation
    cannot dodge the assertions by having nothing else to return.
    """
    license_value = "MIT-0"
    compatibility_value = "Requires ffmpeg 6 or newer and a POSIX shell."
    allowed_tools_value = "Read Write Bash"
    metadata_author = "Field Ops Guild"
    metadata_version = "2.3.1"

    skill_md = (
        "---\n"
        "name: video-transcoder\n"
        "description: Converts video files between common container formats.\n"
        f"license: {license_value}\n"
        f"compatibility: {compatibility_value}\n"
        "metadata:\n"
        f"  author: {metadata_author}\n"
        f'  version: "{metadata_version}"\n'
        f"allowed-tools: {allowed_tools_value}\n"
        "---\n"
        "\n"
        "Probe the input file before choosing an output codec.\n"
    )

    video_transcoder = FakeSkillCandidate(
        directory_name="video-transcoder",
        skill_md_text=skill_md,
    )
    commit_helper = FakeSkillCandidate(
        directory_name="commit-helper",
        skill_md_text=SKILL_MD_COMMIT_HELPER,
    )
    library = SkillLibrary(FakeSkillStorage([commit_helper, video_transcoder]))

    skill = library.get_skill("video-transcoder")

    assert skill.frontmatter.license == license_value
    assert skill.frontmatter.compatibility == compatibility_value
    assert skill.frontmatter.allowed_tools == allowed_tools_value
    assert dict(skill.frontmatter.metadata) == {
        "author": metadata_author,
        "version": metadata_version,
    }


# AC-FEAT-001-028
def test_ac_feat_001_028_get_resource_for_a_zero_byte_file_returns_empty_content_not_resource_not_found() -> None:
    """A file that exists but is zero bytes long returns empty content, and ERR-002 is not raised.

    The contract's return-shape section is explicit about this exact case:
    `get_resource` returns "`b""` for a file that exists and is empty (AC-028)",
    and the ports table repeats it for `read_resource`: "returns `b""` for an
    existing empty file — the two must not collapse into one answer (AC-028)".
    Existing-and-empty is a different fact from absent, and only a raise-free
    return of empty bytes proves the two are not being collapsed into one
    ERR-002 answer the way a truthiness check on the file's content would.

    The storage is wired, through the same `FakeContainedSkillStorage` AC-009
    through AC-011 use, so that `resolve("pdf-processing", "assets/empty.txt")`
    lands on a location that *is* present in the fake's in-memory file map, with
    the value `b""` — deliberately distinct from AC-011, where the miss falls
    out of a location that was never populated at all. If `get_resource` or the
    fake's `read_resource` treated an empty byte string as equivalent to a
    missing key, this would raise `ResourceNotFound` instead of returning.
    """
    skill_root = ("skills", "pdf-processing")
    empty_location = (*skill_root, "assets", "empty.txt")

    pdf_processing = FakeSkillCandidate(
        directory_name="pdf-processing",
        skill_md_text=SKILL_MD_PDF_PROCESSING,
    )
    storage = FakeContainedSkillStorage(
        [pdf_processing],
        skill_roots={"pdf-processing": skill_root},
        files={empty_location: b""},
    )
    library = SkillLibrary(storage)

    try:
        content = library.get_resource("pdf-processing", "assets/empty.txt")
    except Exception as exc:  # noqa: BLE001 - a zero-byte file must not raise ERR-002
        pytest.fail(
            "get_resource must return empty content for a zero-byte file, not "
            f"raise ERR-002 (ResourceNotFound); it raised {type(exc).__name__}: {exc}"
        )

    assert content == b""
