# Frozen interface contract — FEAT-001

frozen_on: 2026-09-16
approved_by: tterrin on 2026-09-16
derives_from: .lasagna/specs/FEAT-001.md

> This document is the **only** thing `test-writer` and `implementer` share. If
> it is ambiguous, the two agents diverge and the loop burns cycles. To change
> it: stop the loop, edit here, re-approve.

## Seams under test

| Seam | Why here | Criteria that pass through |
|---|---|---|
| `httpskills.domain.library.SkillLibrary` | The highest seam that is still pure. All three protocol operations live on it, driven by a fake `SkillStorage`, so every rule of the Agent Skills specification is exercised without a directory on disk. | AC-001 … AC-023, AC-028, AC-029 |
| `httpskills.adapters.mcp_server.create_server` | Authentication and the wire shape cannot be tested below the transport: a token check that passes in-process proves nothing (ADR-0003). | AC-024, AC-025, AC-026, AC-027 |

Two seams, because the split between them is real: one is the protocol's rules,
the other is the protocol's delivery. Nothing else is public.

## Signatures

```python
# httpskills/domain/library.py
class SkillLibrary:
    def __init__(self, storage: SkillStorage) -> None: ...
    def list_skills(self) -> tuple[SkillSummary, ...]: ...
    def get_skill(self, name: str) -> Skill: ...
    def get_resource(self, name: str, path: str) -> bytes: ...


# httpskills/adapters/mcp_server.py
def create_server(library: SkillLibrary, tokens: Sequence[str]) -> FastMCP: ...
```

The three domain operations take `str`, not `SkillName` or `ResourcePath`. The
caller is the transport, and making it build a value object would hand it the
decision of what to do when construction fails — which is a domain decision
(see the error table).

MCP tools registered by `create_server`, and their wire shape:

```python
list_skills()                       -> list[dict[str, str]]   # keys: "name", "description"
get_skill(name: str)                -> str                    # the verbatim SKILL.md
get_resource(name: str, path: str)  -> str                    # UTF-8 decoded
```

## Data types

```python
@dataclass(frozen=True)
class SkillName:
    value: str
    # __post_init__ raises InvalidSkillName unless value satisfies ALL of:
    #   1 <= len(value) <= 64
    #   every character is in a-z, 0-9, or '-'
    #   does not start with '-' and does not end with '-'
    #   contains no '--'


@dataclass(frozen=True)
class ResourcePath:
    value: str
    # __post_init__ raises ResourceNotContained unless value satisfies ALL of:
    #   value is non-empty
    #   value is not an absolute path (no leading '/' or '\', no drive letter)


@dataclass(frozen=True)
class SkillFrontmatter:
    name: SkillName
    description: str                      # 1 <= len <= 1024
    license: str | None                   # None when absent
    compatibility: str | None             # when present, 1 <= len <= 500
    allowed_tools: str | None             # space-separated; not interpreted
    metadata: Mapping[str, str]           # empty mapping when absent
    undefined_keys: Mapping[str, object]  # every key the spec does not define


@dataclass(frozen=True)
class SkillSummary:
    name: SkillName
    description: str


@dataclass(frozen=True)
class Skill:
    frontmatter: SkillFrontmatter
    source_text: str          # the SKILL.md exactly as stored, frontmatter and body


@dataclass(frozen=True)
class SkillCandidate:
    directory_name: str
    skill_md_text: str


@dataclass(frozen=True)
class ResolvedPair:
    skill_root: tuple[str, ...]
    target: tuple[str, ...]


ResolvedLocation = tuple[str, ...]
```

**`SkillSummary` has no field that can hold a Body, and that is the point.**
INV-2 is held by the type, not by remembering to project. A future leak through
Discovery would have to add a field first, which review can see.

**`Skill` carries `source_text`, not a parsed body.** AC-005 and AC-006 demand
the file back verbatim, including keys the specification does not define; a
re-serialised frontmatter is not the same file. Applying the deletion test to a
separate `body` field: nothing in this version reads it, so it is not created.

**A resolved location is a tuple of path segments, never a string.** This is what
makes AC-029 hard to get wrong: comparing `("skills", "demo-evil")` against
`("skills", "demo")` cannot accidentally succeed the way a string prefix test
does. The port splits; the domain compares.

**Deliberately not created.** `Description`, `License` and `Compatibility` as
value objects: their rules are asserted in the one place a frontmatter is
parsed, so wrapping them is a pass-through. A `Catalogue` wrapper class: delete
it and `list_skills` returns the tuple directly — INV-1 is structurally
unreachable (see the domain model), so the wrapper would hold no rule. Aggregate
1 is realised as that return value. When skillsets arrive and filtering becomes
real, a `Catalogue` type may earn its place; it does not today.

## Error types

All derive from `SkillLibraryError`.

| Error | When | Fields | Spec code |
|---|---|---|---|
| `SkillNotFound` | No candidate directory carries this name; or the candidate exists but is not a Valid Skill; or the name cannot be a Skill Name at all | `name: str` | ERR-001 |
| `ResourceNotFound` | The resolved location is inside the skill, but nothing readable is there — absent, or a directory | `name: str`, `path: str` | ERR-002 |
| `ResourceNotContained` | The path is absolute or empty, or its resolved location lies outside the skill's own resolved root | `name: str`, `path: str` | ERR-003 |
| `InvalidSkillName` | Raised by `SkillName.__post_init__` only. **Never escapes a seam** — `SkillLibrary` converts it to `SkillNotFound` | `value: str` | — (internal) |
| `InvalidSkill` | Raised while validating a candidate. **Never escapes a seam** — it causes exclusion from the listing (BR-1) | `directory_name: str`, `reason: str` | — (internal) |

ERR-004 has no domain type. Authentication is the adapter's and is enforced by
fastmcp's `StaticTokenVerifier` before any domain code runs (ADR-0003).

**The two internal errors are the subtlety of this contract.** The same
violation means two different things depending on where it arrives. A bad name
in a *client request* is ERR-001, because an impossible name names nothing. A bad
name in a *stored skill* is exclusion, silently, because BR-1 says an invalid
skill must be indistinguishable from an absent one. Neither internal error may
reach a caller: a test asserting `InvalidSkill` escapes the seam is a wrong test.

## Return shape

**Chosen convention: exceptions.** Every operation returns its value directly
and signals failure by raising. No `Result`, no `None`-as-failure, no boolean
flags, no tuples carrying a status. Value objects validate in `__post_init__`
and raise there. This holds for the whole contract without exception, including
the ports.

- `SkillLibrary.list_skills()` → a tuple of `SkillSummary`, one per Valid Skill,
  in the order the storage yielded candidates. Empty tuple when there are none.
  **Never raises** — an unreadable or invalid candidate is excluded, not
  propagated (BR-1, AC-003, AC-019).
- `SkillLibrary.get_skill(name)` → the `Skill` whose name matches, carrying the
  `SKILL.md` verbatim in `source_text`. Raises `SkillNotFound`.
- `SkillLibrary.get_resource(name, path)` → the file's bytes. `b""` for a file
  that exists and is empty (AC-028). Raises `SkillNotFound`,
  `ResourceNotContained`, `ResourceNotFound`.
- `create_server(library, tokens)` → a configured `FastMCP` instance, not
  started. Starting it is the caller's.

## Required ports

One port. The domain depends on it; it depends on nothing.

| Port | Signature | Why it is needed | Planned adapter |
|---|---|---|---|
| `SkillStorage.list_candidates` | `def list_candidates(self) -> Sequence[SkillCandidate]: ...` | The only way the catalogue is read. Yields two strings per candidate — the directory's *name* and the raw `SKILL.md` text — and nothing that can be read from (ADR-0001). A directory with no `SKILL.md` is simply not yielded. | `FilesystemSkillStorage` |
| `SkillStorage.resolve` | `def resolve(self, directory_name: str, relative_path: str) -> ResolvedPair: ...` | Follows symlinks and returns both real locations as segment tuples. Reads nothing, decides nothing, and succeeds even when the target does not exist (ADR-0002, step 2). | `FilesystemSkillStorage` |
| `SkillStorage.read_resource` | `def read_resource(self, location: ResolvedLocation) -> bytes: ...` | Reads a location the domain has already judged contained. Raises `ResourceNotFound` when nothing readable is there, and returns `b""` for an existing empty file — the two must not collapse into one answer (AC-028). | `FilesystemSkillStorage` |

**`resolve` must not return a verdict.** It returns two locations; the domain
compares them. A port that returned a boolean would move INV-3 into the adapter
and quietly reverse ADR-0002.

**No port declares a write.** INV-4 is held by what does not exist here.

**Known consequence, stated rather than discovered**: `get_skill` and
`get_resource` locate their skill through `list_candidates()`, so they read every
`SKILL.md` to serve one. This is deliberate — it keeps the port to a single
read path and satisfies BR-3 exactly — and it is affordable only under A5
(dozens of skills). It is the first thing to change if the library grows, and it
changes the port, not the domain.

## Determinism

| Source | How it enters the domain |
|---|---|
| Filesystem | port `SkillStorage` — the only outside contact the domain has |
| Current time | not needed; nothing in this feature depends on it |
| Randomness, ids | not needed; identity is the Skill Name, which comes from the data |
| Environment (skills root path, token set) | resolved at the edge in the composition root and passed in as arguments; never read inside the core |

## What is NOT frozen

The implementer decides these alone; a test that depends on them is a wrong test
and the referee should say so.

- How a `SKILL.md` is split into frontmatter and body, and which YAML parser is
  used.
- Whether validation lives in one function or several, and the wording of any
  `reason` string.
- The internal containment predicate — its name, its location, its signature.
  What is frozen is that `resolve` returns segment tuples and the domain does the
  comparing.
- The order of checks inside an operation, except where the spec fixes it: a
  path that is absolute is rejected before any resolution (AC-012 says no file is
  read), and an unknown skill name is reported (`SkillNotFound`) before its path
  is validated at all, even when the path is also absolute or empty (AC-038) —
  `get_resource` checks skill existence first, path validity second.
- Any caching, indexing or memoisation **is forbidden**, not unfrozen — BR-3.
- How `FilesystemSkillStorage` walks the directory, and how the composition root
  parses the environment.
