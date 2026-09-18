# Spec — FEAT-001: httpskills, a centralised Agent Skills library over MCP

feature_id: FEAT-001
flow: official
status: approved
approved_by: tterrin on 2026-09-16

## Goal

An MCP client holding a valid bearer token can discover, load and read the
bundled resources of Agent Skills that live in one place on a server, instead of
carrying a duplicated copy of that knowledge in every project. What the server
exposes is faithful to the Agent Skills specification
(https://agentskills.io/specification), not a simplified variant of it.

## Non-goals

- **Skillsets.** Deferred to a later version. Any valid token reads every skill.
  Building the abstraction now would cost code the beta does not need.
- **Any write path.** No create, update or delete of a skill through MCP. Skills
  reach the server by the operator's hand, outside this feature.
- **OAuth, token issuance, expiry or rotation logic.** The token is "symbolic":
  a static set of strings checked by the server. Anything more is a later
  decision, not a simplification of this one.
- **Caching and invalidation.** The catalogue is read from the filesystem on
  every call. A cache would add an invalidation problem the demo does not have.
- **Executing or validating the content of `scripts/`.** The server serves those
  files as bytes; it never runs them and never judges them.
- **Rendering or transforming Markdown.** `get_skill` returns the real file, not
  a re-rendered one, because re-rendering is how fidelity gets lost.
- **Authoring the production skills.** Exactly one test skill ships with this
  feature. The real library is added by the operator, outside this spec.
- **TLS termination.** A deployment concern, assumed, not enforced here.

## Architectural constraints and assumptions

From the grilling. Stated, never silent.

- **Asynchrony**: none. All three tools are synchronous reads of one local
  filesystem. No queue, no background job, no eventual consistency.
- **Consistency**: no staleness window. The catalogue is read through on every
  call, so a skill added or edited on disk is visible to the next call without a
  restart. The cost is a directory walk per `list_skills`, which is acceptable
  only because of the volume assumption below.
- **Contention**: moot in v1. No operation writes, so two simultaneous callers
  cannot conflict. Two readers observing the filesystem mid-edit is possible in
  principle; at demo scale, with an operator editing by hand, it is accepted
  rather than defended against.
- **Partial failure**: there is no second system to fail. The only partial
  failure that exists is one malformed skill among many, and it is contained by
  BR-1: that skill excludes itself, the listing still succeeds. All three tools
  are pure reads, therefore idempotent and safely retryable.
- **Volumes**: dozens of skills, demo scale. This is the assumption that makes
  read-through free; at thousands of skills `list_skills` would need a cache and
  the consistency answer above would have to be reopened.
- **Technology constraints already decided**: Python 3.12, `uv`, fastmcp 4.0.4
  over HTTP transport, `StaticTokenVerifier` for bearer auth, filesystem
  storage, no database.

## System use cases

### UC-1 — Discover the available skills

- **Actor**: MCP Client (authenticated)
- **Pre-conditions**: the client presents a bearer token present in the server's
  token registry. A skills root directory exists on the server.
- **Post-conditions**: the client holds the `name` and `description` of every
  valid skill, and no instruction body of any skill. The filesystem is unchanged.
- **Main scenario**:
  1. The client calls `list_skills()`.
  2. The server reads the skills root from the filesystem.
  3. For each candidate directory, the server parses `SKILL.md` and validates it
     against the Agent Skills specification.
  4. The server returns one entry per valid skill, carrying `name` and
     `description` only.
- **Alternative flows**:
  - 2a. The skills root contains no skill → an empty list, not an error.
  - 3a. A candidate fails validation → it is omitted; the remaining skills are
    still returned and the call still succeeds.

### UC-2 — Load a skill's instructions

- **Actor**: MCP Client (authenticated)
- **Pre-conditions**: the client knows a skill `name`, typically from UC-1.
- **Post-conditions**: the client holds the exact content of that skill's
  `SKILL.md`. The filesystem is unchanged.
- **Main scenario**:
  1. The client calls `get_skill(name)`.
  2. The server locates the skill directory whose name is `name` and validates it.
  3. The server returns the content of `SKILL.md` verbatim — YAML frontmatter,
     including keys the specification does not define, followed by the Markdown
     body.
- **Alternative flows**:
  - 2a. No skill directory carries that name → ERR-001.
  - 2b. The directory exists but fails validation → ERR-001. An invalid skill is
    indistinguishable from an absent one (BR-1).

### UC-3 — Read a resource bundled with a skill

- **Actor**: MCP Client (authenticated)
- **Pre-conditions**: the client knows a skill `name` and a path relative to that
  skill's directory, typically read from the body returned by UC-2.
- **Post-conditions**: the client holds the content of that file. The filesystem
  is unchanged.
- **Main scenario**:
  1. The client calls `get_resource(name, path)`.
  2. The server locates and validates the skill directory as in UC-2.
  3. The server resolves `path` against the skill's directory, following symlinks
     to their real target.
  4. The server confirms the resolved real path lies inside that skill's
     directory.
  5. The server returns the file's content.
- **Alternative flows**:
  - 2a. Unknown or invalid skill → ERR-001.
  - 3a. `path` is absolute → ERR-003, refused before any filesystem access.
  - 4a. The resolved path lies outside the skill directory, whether reached by
    `..` segments or by a symlink → ERR-003.
  - 5a. Nothing exists at the resolved path, or it is a directory → ERR-002.

### UC-4 — Authenticate

- **Actor**: MCP Client
- **Pre-conditions**: the server was started with a non-empty token registry read
  from the environment.
- **Post-conditions**: on success the client may call all three tools; on failure
  it learns nothing about the catalogue.
- **Main scenario**:
  1. The client sends a bearer token with the request.
  2. The server compares it against the registry.
  3. The request proceeds.
- **Alternative flows**:
  - 1a. No token presented → ERR-004.
  - 2a. Token absent from the registry → ERR-004.

## Acceptance criteria

| ID | Given | When | Then |
|---|---|---|---|
| AC-FEAT-001-001 | a skills root holding three valid skills | `list_skills()` is called | three entries are returned, each carrying exactly the `name` and `description` read from its `SKILL.md` |
| AC-FEAT-001-002 | a valid skill whose `SKILL.md` body contains a recognisable instruction string | `list_skills()` is called | no part of that body appears anywhere in the response |
| AC-FEAT-001-003 | a skills root holding two valid skills and one whose `name` does not match its directory | `list_skills()` is called | the call succeeds and returns exactly the two valid skills |
| AC-FEAT-001-004 | a skills root containing no skill directory | `list_skills()` is called | an empty list is returned and no error is raised |
| AC-FEAT-001-005 | a valid skill `demo-skill` | `get_skill("demo-skill")` is called | the returned content is byte-for-byte the content of that skill's `SKILL.md`, frontmatter and body included |
| AC-FEAT-001-006 | a valid skill whose frontmatter carries a key the specification does not define, alongside `name` and `description` | `get_skill` is called for it | the skill is valid, and the undefined key and its value appear unchanged in the returned content |
| AC-FEAT-001-007 | a skills root with no directory named `absent-skill` | `get_skill("absent-skill")` is called | ERR-001 is raised |
| AC-FEAT-001-008 | a skill directory that exists on disk but fails validation | `get_skill` is called with its directory name | ERR-001 is raised — the same error as an absent skill, with no detail distinguishing the two |
| AC-FEAT-001-009 | a valid skill carrying `references/REFERENCE.md` | `get_resource(name, "references/REFERENCE.md")` is called | the file's content is returned |
| AC-FEAT-001-010 | a valid skill carrying `assets/template.txt` | `get_resource(name, "assets/template.txt")` is called | the file's content is returned |
| AC-FEAT-001-011 | a valid skill with no file at `references/missing.md` | `get_resource(name, "references/missing.md")` is called | ERR-002 is raised |
| AC-FEAT-001-012 | a valid skill | `get_resource` is called with an absolute path | ERR-003 is raised and no file is read |
| AC-FEAT-001-013 | a valid skill, and a readable file outside its directory | `get_resource` is called with a path escaping the directory through `..` segments | ERR-003 is raised and the outside file's content is not returned |
| AC-FEAT-001-014 | a valid skill containing a symlink whose target lies outside the skill directory | `get_resource` is called with the symlink's path | ERR-003 is raised and the target's content is not returned |
| AC-FEAT-001-015 | a skills root with no directory named `absent-skill` | `get_resource("absent-skill", "references/any.md")` is called | ERR-001 is raised |
| AC-FEAT-001-016 | a skill directory `demo-skill` whose `SKILL.md` declares `name: other-name` | the catalogue is read | the skill is invalid and absent from the catalogue |
| AC-FEAT-001-017 | skill directories whose declared `name` is, in turn, empty, longer than 64 characters, `Demo-Skill`, `-demo`, `demo-`, or `demo--skill` | the catalogue is read | each one is invalid and absent from the catalogue |
| AC-FEAT-001-018 | skill directories whose `description` is, in turn, absent, empty, and longer than 1024 characters | the catalogue is read | each one is invalid and absent from the catalogue |
| AC-FEAT-001-019 | a `SKILL.md` with no frontmatter at all, and one whose frontmatter is malformed YAML | the catalogue is read | each one is invalid and absent from the catalogue, and no exception escapes the catalogue read |
| AC-FEAT-001-020 | a skill whose `compatibility` exceeds 500 characters | the catalogue is read | the skill is invalid and absent from the catalogue |
| AC-FEAT-001-021 | a skill whose `metadata` is not a mapping of string keys to string values | the catalogue is read | the skill is invalid and absent from the catalogue |
| AC-FEAT-001-022 | a skill declaring only `name` and `description` | the catalogue is read | the skill is valid and present in the catalogue |
| AC-FEAT-001-023 | a skill declaring `name`, `description`, and well-formed `license`, `compatibility`, `metadata` and `allowed-tools` | the catalogue is read | the skill is valid and present in the catalogue |
| AC-FEAT-001-024 | a running server with a non-empty token registry | a request carrying no bearer token calls any of the three tools | ERR-004 is raised and no catalogue content is returned |
| AC-FEAT-001-025 | a running server whose registry holds `token-a` | a request bearing `token-b` calls any of the three tools | ERR-004 is raised and no catalogue content is returned |
| AC-FEAT-001-026 | a running server whose registry holds two distinct tokens | each token in turn calls `list_skills`, `get_skill` and `get_resource` | every call succeeds identically — v1 draws no distinction between tokens |
| AC-FEAT-001-027 | the test skill shipped with this feature | the server is started against it and the three tools are called in sequence | the skill is listed, its `SKILL.md` is returned, and its `references/` and `assets/` files are returned — over the real MCP transport, not an in-process stub |
| AC-FEAT-001-028 | a valid skill carrying a zero-byte file at `assets/empty.txt` | `get_resource(name, "assets/empty.txt")` is called | empty content is returned successfully; ERR-002 is **not** raised, because existing-and-empty is not the same answer as absent |
| AC-FEAT-001-029 | a skill directory `demo` and a sibling directory `demo-evil` holding a readable file, both under the skills root | `get_resource("demo", …)` is called with a path resolving into `demo-evil` | ERR-003 is raised — containment compares whole path segments, so a sibling whose name merely extends the skill's is not inside it |

| AC-FEAT-001-030 | a valid skill declaring well-formed `license`, `compatibility`, `metadata` and `allowed-tools` | `get_skill` is called for it | each of those four fields comes back with the value actually declared, not a placeholder |
| AC-FEAT-001-031 | a `SKILL.md` whose frontmatter is syntactically valid YAML but is missing the required `name` key, or whose top-level YAML value is not a mapping at all | the catalogue is read | the skill is invalid and absent from the catalogue, and no exception escapes the catalogue read |
| AC-FEAT-001-032 | a valid skill | `get_resource` is called with an empty string as `path` | ERR-003 is raised and no file is read |
| AC-FEAT-001-033 | a storage double whose candidates change between two calls | `list_skills()` is called, the double's candidates are then changed, and `list_skills()` is called again | the second call's result reflects the new candidates, not the first — proving BR-3 (no caching, no memoisation) |
| AC-FEAT-001-034 | a skill declaring only `name` and `description` (no optional fields at all) | `get_skill` is called for it | `license`, `compatibility` and `allowed_tools` come back `None`, and `metadata` comes back an empty mapping — not a placeholder value |
| AC-FEAT-001-035 | a storage double whose candidates change between two calls | `get_skill(name)` is called, the double's candidates are then changed so that `name` no longer resolves, and `get_skill(name)` is called again | the second call raises `SkillNotFound` — proving BR-3 for `get_skill`, not only for `list_skills` |
| AC-FEAT-001-036 | a skill whose `compatibility` is a non-string YAML value (for example a number or a boolean) | the catalogue is read | the skill is invalid and absent from the catalogue, the same as a `compatibility` that is a too-long string |
| AC-FEAT-001-037 | a skill directory that exists on disk but fails validation | `get_resource` is called with its directory name and any relative path | `SkillNotFound` is raised — the same error `get_skill` raises for the identical directory (AC-008), not `InvalidSkill` or `InvalidSkillName` leaking, and not `ResourceNotFound` |
| AC-FEAT-001-038 | a skills root with no directory named `absent-skill` | `get_resource("absent-skill", path)` is called with `path` itself also invalid (empty, or absolute) | `SkillNotFound` is raised, not `ResourceNotContained` — an unknown skill is reported before its path is even considered |

Criteria 028 and 029 were added after gate 1, during domain modelling: the
mandated stress test surfaced two behaviours the original table did not pin
down. They carry new ids and supersede nothing.

Criteria 030 and 031 were added after adversarial review of the domain layer's
green suite: AC-006 exercised only `undefined_keys`, leaving `get_skill`'s
four defined optional fields unverified — `get_skill` was in fact hardcoding
them to placeholder values, discarding real declared content. AC-019 exercised
only "no frontmatter" and "unparseable YAML", leaving "valid YAML missing
`name`" and "valid YAML that isn't a mapping" unverified — both crashed with an
uncaught `KeyError`/`TypeError` instead of the same silent-exclusion behaviour
BR-1 requires. They carry new ids and supersede nothing.

Criteria 032 and 033 were added closing out the second adversarial-review
pass's open items. AC-012 exercised only an absolute path, leaving the
contract's other construction rule for `ResourcePath` — non-empty — wholly
unverified; the implementation's `_is_absolute` check does not reject `""`,
so an empty path was falling through to `storage.resolve` uncaught, a real
gap, not a hypothetical one. Nothing in the suite exercised BR-3 directly:
every existing test reads a storage double once, so a library that secretly
cached its first read would still pass all 31 prior criteria. AC-033 closes
that hole at the seam, without needing a real filesystem. They carry new ids
and supersede nothing.

Two other adversarial-review items were considered and deliberately **not**
turned into criteria:

- The dead redundant `if summary.name.value == name:` check inside
  `get_skill`/`get_resource` (`library.py`) is unreachable given
  `_summarise`'s own validation and the loop's directory-name filter — no
  criterion describes it because no observable behaviour depends on it. It is
  removed as cleanup, not as a tdd-loop cycle.
- The untested "resource is a directory" alt-flow for AC-011 is not a domain
  gap: `SkillLibrary.get_resource` only calls `storage.read_resource(location)`
  and propagates whatever it raises (contract: `ResourceNotFound` — "absent, or
  a directory"). Telling a directory apart from an absent file is a filesystem
  fact only `FilesystemSkillStorage` can produce; a domain-level fake that
  "detects a directory" would just be told to raise `ResourceNotFound`, adding
  no assurance beyond what AC-011 already proves about propagation. This
  belongs to the `ports-adapters` phase (AC-024 … AC-027's layer), not this
  domain loop — flagged there, not skipped.

Criteria 034, 035, 036 and 037 were added closing out the third
adversarial-review pass. AC-030 only proved the "declared" half of optional-field
handling, leaving the "absent" half — `None`/`{}` rather than a placeholder —
wholly unverified; AC-034 closes that hole. AC-033 proved BR-3 only for
`list_skills`; the contract's own "Known consequence" note states that
`get_skill` and `get_resource` are equally bound by BR-3 because they too
resolve through `list_candidates()`, and nothing exercised that; AC-035 closes
it for `get_skill` (the same fake-storage-mutation shape as AC-033).
`compatibility`'s length check (`isinstance(compatibility, str) and len(...) >
500`) silently accepts any non-string value — a real, confirmed gap parallel to
the AC-032 empty-path gap, since the domain model declares `compatibility: str |
None`; AC-036 closes it, mirroring AC-021's pattern for `metadata`. AC-008
verifies that `get_skill` on an existing-but-invalid directory raises
`SkillNotFound`, but no criterion exercises the identical case for
`get_resource`, even though the code already appears to handle it correctly;
AC-037 closes that verification gap. They carry new ids and supersede nothing.

Two further items from the third pass were considered and deliberately **not**
turned into criteria, for now:

- **`ResourcePath` does not exist as a type.** The contract's Data types
  section specifies it as a frozen dataclass whose `__post_init__` raises
  `ResourceNotContained` for an absolute or empty value. The implementation
  instead inlines the equivalent check directly in `get_resource` (`path == ""
  or _is_absolute(path)`). Behaviourally equivalent today (AC-012/AC-032 both
  pass), but the structural guarantee the contract describes — the check being
  unskippable at construction, not by discipline — does not exist: a future
  second call site could simply forget it. This is a contract-compliance gap,
  not a behavioural one; no criterion can close it (nothing observable would
  differ), so it is queued as a **cleanup task** — introduce `ResourcePath` in
  `domain/model.py` per the contract and have `get_resource` construct one
  instead of the inline boolean check — verified by full-suite regression, not
  a new tdd-loop cycle.
- **Check-ordering ambiguity in `get_resource`** when the skill name is unknown
  **and** the path is absolute/empty at once: today the path check runs first,
  so this combination raises `ResourceNotContained` (ERR-003), not
  `SkillNotFound` (ERR-001). AC-015 only tests "unknown skill + relative path"
  and AC-012/AC-032 only test "known-good skill + bad path" — no criterion
  exercises both conditions together. The contract's "What is NOT frozen"
  section leaves check ordering open except "absolute rejected before
  resolution" (AC-012), so today's behaviour is not a violation — it is an
  undecided ambiguity, not yet a gap with one correct answer.

This ambiguity was resolved by the user: an unknown skill name must be reported
before its path is even considered, because reporting the wrong path detail for
a name that was never going to resolve is more misleading than useful, and a
dedicated third error type for this one narrow overlap was judged not worth its
own weight. AC-FEAT-001-038 codifies the decision: `SkillNotFound` wins over
`ResourceNotContained` when both conditions hold. This narrows the contract's
"order of checks is free" clause with one more named exception, alongside the
existing "absolute rejected before resolution" one — a documentation-only
contract amendment, no signature affected.

Mutation testing (`mutmut`) remains unrunnable in this environment: it is not
installed, and adding it as a dev dependency fails during `uv add` on an
unrelated Windows/uv packaging error (`trove_classifiers` build, PE-resource
access denied on the uv trampoline), not on anything about `mutmut` itself.
This is an environment limitation stated in `.lasagna/stack.md`'s own note
("please use the WSL") and remains an open risk to be resolved outside this
loop, most likely by running the suite under WSL rather than native Windows.

## Domain invariants

Always true, at every instant.

- **INV-1**: every skill present in the catalogue has a `name` unique across the
  whole server. *Not testable in isolation*: the specification forces `name` to
  equal the parent directory name (AC-FEAT-001-016) and a filesystem cannot hold
  two sibling directories with the same name, so a duplicate is structurally
  unreachable. It is recorded here because it is a promise to the future: when
  skillsets arrive they must filter a flat namespace rather than partition it,
  or `get_skill(name)` becomes ambiguous and its signature breaks.
- **INV-2**: no response of `list_skills` ever contains any part of any skill's
  instruction body. This is the progressive disclosure of the specification,
  held as an invariant rather than a behaviour, because a leak here silently
  defeats the entire point of the server.
- **INV-3**: every byte returned by `get_resource` comes from a file whose
  resolved real path lies inside the requested skill's own directory.
- **INV-4**: no tool exposed in v1 modifies the filesystem in any way.

## Business rules

Conditional, therefore not invariants.

- **BR-1**: when a skill fails validation, it is excluded from the catalogue and
  becomes indistinguishable from a skill that does not exist — same error, no
  distinguishing detail. One invalid skill never causes a catalogue read to fail.
- **BR-2**: when a frontmatter key is not defined by the specification, it is
  ignored for validation and preserved unchanged in `get_skill`'s output.
- **BR-3**: when the catalogue is consulted, it is read from the filesystem at
  that moment; no result of a previous read is reused.

## Error taxonomy

| Code | Cause | What the user sees | Retryable |
|---|---|---|---|
| ERR-001 | The named skill does not exist, or exists on disk but fails validation | "Unknown skill: `<name>`" — identical in both cases | no — deterministic until the operator changes the skill on disk |
| ERR-002 | The path resolves inside the skill directory but nothing readable is there | "No resource at `<path>` in skill `<name>`" | no — deterministic |
| ERR-003 | The path is absolute, or its resolved real path falls outside the skill directory | "Path `<path>` is outside skill `<name>`" | no — the request is malformed, retrying it changes nothing |
| ERR-004 | No bearer token presented, or the token is absent from the registry | Transport-level rejection; no catalogue information whatsoever | yes — with a token that is in the registry |

## Verification and rollback plan

Per vertical slice, in build order. Nothing in v1 writes to a database or emits
an external effect, so the only thing that can escape the system is a token.

| # | Slice | How we verify it is right | How we get back |
|---|---|---|---|
| 1 | Frontmatter parsing and specification validation (pure domain) | AC-016 through AC-023 against in-memory content; cross-checked against `skills-ref validate` on the test skill as an outside opinion | Revert the commit. Pure functions, nothing ran, nothing persisted. |
| 2 | Catalogue: list and lookup by name over a storage port (domain + port) | AC-001 through AC-008 against a fake in-memory storage port | Revert the commit. The port has no implementation yet, so nothing outside the domain can have called it. |
| 3 | Resource resolution and containment (domain + port) | AC-009 through AC-015, containment cases first | Revert the commit. If slice 4 already shipped, revert this one too — a half-reverted containment rule is worse than either whole. |
| 4 | Filesystem adapter implementing the storage port | Slices 2 and 3 re-run against a real temporary directory, including a real symlink for AC-014 | Revert the commit. The adapter only reads; no file it touched was changed. |
| 5 | fastmcp MCP adapter, HTTP transport, `StaticTokenVerifier` wiring | AC-024 through AC-026 against the running server | Revert the commit **and rotate every token in the environment**. Once the server has been reachable, any token that was configured must be treated as disclosed; reverting code does not un-disclose it. |
| 6 | The test skill fixture and the end-to-end pass | AC-027 over the real transport | Delete the fixture directory. It holds no real content, so nothing of value is lost. |

## Open questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| Q1 | Is there a maximum size for a resource served by `get_resource`? `assets/` may legitimately hold a large binary, and the whole file is read into memory and into the client's context. At demo scale this is theoretical; it stops being theoretical the first time someone commits a PDF. | user | no — v1 serves whatever is there; a limit can be added without changing any signature |
| Q2 | Should the server log which skill each token reads? Useful for knowing which knowledge is actually used, and it is the natural seam for the future skillset work. | user | no — additive, touches no criterion here |
| Q3 | Is an optional key declared with an empty value "present"? `compatibility:` with nothing after it parses to `None`, not `""`. The specification says `compatibility` must be 1–500 characters *if provided*, and never says whether a bare key counts as provided. Raised during the AC-020 cycle by the implementer, who declined to guess. Currently treated as absent, therefore valid. | user | no — no criterion covers it either way; decide it and it becomes a new criterion |

## Notes for the phases that follow

- `CONTEXT.md` does not exist yet. `domain-modeling` creates it; the vocabulary
  this spec uses deliberately — *skill*, *catalogue*, *frontmatter*, *resource*,
  *token registry* — is the input to that step, not a substitute for it.
- The stated project goal, "verify correct use of fastmcp from its real
  documentation", is a project constraint and is deliberately **not** an
  acceptance criterion: it is not a promise to a user and it is not testable.
  What is testable is fidelity to the Agent Skills specification, which
  AC-016 through AC-023 cover, with `skills-ref validate` available as an
  outside check written by neither of us.

## Domain model

Vocabulary is fixed in `CONTEXT.md`; the capitalised terms below are its terms.
Related decisions: ADR-0001, ADR-0002, ADR-0003.

### The shape in one line

The aggregates are the three levels of Progressive Disclosure: the **Catalogue**
is level one, a **Skill** is level two, a **Resource** is level three. Each level
is reached only by asking for it, and each holds strictly more than the one
before. This is not a coincidence to be tidied away later — it is why the model
has three pieces instead of one.

### Value objects

| Value object | Why it exists (deletion test) |
|---|---|
| **SkillName** | Delete it and the format rules — length, alphabet, hyphen placement — reappear at every entry point, because a name arrives from outside on both Activation and Resource reads, not only from parsing. It also carries the relational rule `name == Skill Directory name`. Kept: validation at construction, and it is the identity every aggregate references. |
| **ResourcePath** | Delete it and INV-3's first line of defence becomes a check a caller can forget. Kept: it cannot be constructed from an absolute or empty path, so the syntactic half of containment is unskippable (ADR-0002, step 1). |
| **SkillFrontmatter** | The parsed Frontmatter as a whole: the two required fields, the four optional ones, and every Undefined Key preserved. Kept because validity is a property of the Frontmatter as a unit, not of any one field. |
| **SkillSummary** | SkillName plus description, and structurally incapable of holding a Body. Kept because this is what makes INV-2 true by construction rather than by discipline — see below. |

**Deliberately not value objects.** `description`, `license`, `compatibility`
and `allowed-tools` stay primitives inside `SkillFrontmatter`. Applying the
deletion test to each: their rules are asserted in exactly one place either way,
because there is exactly one place a Frontmatter is parsed. A `Description(str)`
whose only content is a length check is the pass-through the test is meant to
catch. `SkillName` is the exception precisely because it does *not* arrive only
from parsing.

### Entities

| Entity | Identity | Notes |
|---|---|---|
| **Skill** | SkillName | A Valid Skill in full: its SkillFrontmatter and its Body. Immutable — identity, not mutability, is what makes it an entity here, since the same SkillName denotes the same Skill across reads even as the operator edits the file underneath. |

**Deliberately not an entity.** A Resource has no identity of its own: it is
content addressed by the pair (SkillName, ResourcePath). Applying the deletion
test — inline it into the read operation — no invariant and no state transition
reappears. It stays a returned value.

### Aggregates

Because nothing in this version writes, an aggregate boundary here is a
consistency-of-read boundary rather than a transaction boundary. Saying so is
more useful than pretending otherwise: it is why the usual two-writer questions
have short answers.

**Aggregate 1 — Catalogue** · root: `Catalogue`

- **Boundary**: the set of SkillSummary, one per SkillName. It holds summaries,
  never Bodies.
- **Invariants held**: **INV-1** (every SkillName in the set is unique) and
  **INV-2** (nothing in the set can carry a Body).
- **References outward**: by SkillName only. The Catalogue never holds a Skill.
- **Rules**: BR-1 — a candidate that is not a Valid Skill never enters, and the
  set is still built from the rest. BR-3 — the set is rebuilt from the Skills
  Root whenever it is consulted.

INV-2 is held **structurally**. The Catalogue is typed as a set of SkillSummary,
and a SkillSummary has nowhere to put a Body. A future change cannot leak the
Body through Discovery by carelessness; it would have to change the type first,
which is a visible act. This is the whole reason SkillSummary exists as a
separate value object rather than as a convention about which fields to read.

INV-1 is held but **not testable in isolation**, and the model says so rather
than inventing a test that cannot fail: `name == Skill Directory name` plus a
filesystem that cannot hold two sibling directories with one name makes the
duplicate unreachable. It is recorded because it is a promise to the deferred
skillset work — that feature must *filter* this flat namespace, never partition
it, or Activation by SkillName becomes ambiguous.

**Aggregate 2 — Skill** · root: `Skill`

- **Boundary**: one SkillName, one SkillFrontmatter, one Body. Its Resources are
  outside the boundary: they are reached through the Skill, not contained in it,
  which is what keeps Activation from dragging every bundled file into memory.
- **Invariants held**: the Skill is a Valid Skill — it cannot be constructed
  otherwise, so an invalid Skill has no representation in the model at all. This
  is what makes BR-1's indistinguishability structural: there is no object to
  return and no branch to accidentally expose one.
- **References outward**: Resources by ResourcePath, relative to this Skill.

**Aggregate 3 — Resource access** · root: none; a domain service over (Skill,
ResourcePath)

- **Boundary**: one containment decision.
- **Invariants held**: **INV-3**. Split across the layers per ADR-0002 — the
  domain refuses absolute paths at construction, the port resolves real
  locations, and a pure domain function returns the verdict. The read is a
  separate port call, reachable only after an affirmative verdict.
- The containment comparison is **path-segment aware, not textual prefix**. The
  case that decides the implementation is a sibling whose name extends the
  Skill's: `/skills/demo-evil` must not be judged contained in `/skills/demo`.

**INV-4** belongs to no aggregate. It is a property of the port surface: no port
declared in this version exposes an operation that writes. It is held by what
does not exist, and the way to break it is to add something.

### Cross-aggregate references

```
Catalogue ──holds──▶ SkillSummary ──by SkillName──▶ Skill ──by ResourcePath──▶ Resource
             (level 1)                    (level 2)                  (level 3)
```

No aggregate holds a direct reference to another. Discovery yields SkillNames;
Activation takes a SkillName; a Resource read takes a SkillName and a
ResourcePath. Each arrow is a separate client request, which is Progressive
Disclosure expressed as the model's reference structure.

### Where authorization is not

The domain has no Token, principal or grant concept in this version (ADR-0003).
Every caller that reaches the domain has already been authenticated and is
entitled to the whole Catalogue.

### Stress test

| Scenario | The model's answer |
|---|---|
| Two clients read while the operator edits a `SKILL.md` | Each read sees one whole file, old or new. Across two Skills a single Discovery may see one old and one new — acceptable, because no invariant spans two Skills except INV-1, which the filesystem enforces regardless of timing. |
| A Skill is deleted between Discovery and Activation | ERR-001, identical to a name that never existed. BR-1 already makes deleted, invalid and absent indistinguishable, so no new case appears. |
| A Skill's `SKILL.md` becomes invalid between Discovery and Activation | ERR-001. The client holds a stale SkillSummary, which BR-3 makes unavoidable and harmless: the Catalogue is a snapshot of the moment it was asked for, never a promise about later. |
| Empty Skills Root | An empty Catalogue, which is valid — not an error (AC-FEAT-001-004). |
| A Resource file exists but is zero bytes | Empty content is returned, **not** ERR-002. Existing-and-empty and not-existing are different answers, and the port must distinguish them rather than collapsing both into a falsy read. |
| A directory under the Skills Root with no `SKILL.md` | Not a candidate at all; it never reaches validation. Absent from the Catalogue for a different reason than an invalid Skill, though the client cannot tell (ADR-0001). |
| The Skill Directory is itself a symlink to elsewhere | Permitted. Containment is judged against that Skill Directory's own resolved location, so everything inside it is still contained. Only the operator can create this, and no client can exploit it. |
| A Resource read fails after Discovery succeeded | ERR-001 or ERR-002 and nothing else. There is no partial state to unwind, because no step wrote anything — which is the whole reason the partial-failure answer in this spec is short. |
| Volume ceiling | Unbounded in this version: open question Q1. A single Resource is read whole into memory, so the ceiling is a large file in `assets/`, not the number of Skills. |
