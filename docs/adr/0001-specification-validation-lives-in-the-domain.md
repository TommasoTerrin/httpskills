# ADR-0001 — Specification validation lives in the domain, not in the filesystem adapter

status: accepted
date: 2026-09-16
origin_feature: FEAT-001

## Context

Fidelity to the Agent Skills specification is the reason this project exists, and
it is expressed almost entirely as rules over a Frontmatter: `name` shape and
length, `description` length, `compatibility` length, `metadata` being a mapping
of strings to strings. One of those rules is relational rather than syntactic —
a Skill's `name` must equal the name of its Skill Directory — and a directory
name is a fact only the filesystem knows. That single rule is what pulls
validation towards the adapter, because the adapter is the only component allowed
to look at a directory.

## Decision

Validation lives in the domain. The adapter's job is to hand the domain two
pieces of data: the name of the candidate directory, and the raw text of its
`SKILL.md`. The domain decides, from those two strings alone, whether a Valid
Skill exists. The directory-name rule is therefore checked by comparing two
values the domain already holds, not by inspecting a filesystem.

## Alternatives rejected

- **Validate in the filesystem adapter, pass only well-formed Skills inward**:
  rejected because the rules of the specification would then live in the one
  layer that cannot be unit-tested without a real directory tree, and because a
  second adapter — a future Git-backed or HTTP-backed store — would have to
  reimplement all of them, which is precisely how two implementations drift into
  two different notions of "valid".
- **Validate at the MCP boundary, on the way out**: rejected because a Skill's
  validity decides whether it is in the Catalogue at all (BR-1); deciding that at
  the edge means the Catalogue transiently contains Skills that must not exist,
  and INV-1 would be asserted over a set that has not been filtered yet.
- **Delegate to the `skills-ref` reference validator**: rejected as the primary
  mechanism because it is an external process, which the domain may not invoke,
  and because a rule we do not own cannot be asserted per-field in tests. It is
  retained as an independent cross-check in the verification plan, which is the
  role it is actually good at.

## Consequences

Every rule of the specification becomes a pure function over two strings, so each
one is a unit test with no fixture directory. Adding a second storage adapter
later costs nothing in validation, since a new adapter supplies the same two
strings.

The non-obvious cost: the domain now depends on a concept that smells like
storage — "the name of the containing directory" — and someone will eventually
propose passing a richer filesystem object instead. That must be refused. What
crosses the boundary is the directory's *name*, a plain string, never a path, a
handle, or anything that can be read from. The moment a path object crosses, the
domain can do I/O and this decision has quietly been reversed.

A second cost: a directory with no `SKILL.md` at all and a directory with a
malformed one are both absent from the Catalogue, but they are not the same
thing. The first was never a candidate; the second is a candidate that failed.
The domain only ever sees the second, because the adapter cannot hand over text
that does not exist. Operator-facing diagnostics that want to tell these apart
must get that from the adapter, not from validation.
