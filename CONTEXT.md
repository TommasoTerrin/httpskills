# httpskills

A single place where Agent Skills live, served to AI agents over MCP. The
knowledge is centralised here instead of duplicated in every project that needs
it, and what is served is faithful to the Agent Skills specification
(https://agentskills.io/specification) rather than a house variant of it.

## Language

**Skill**:
A unit of packaged expertise: one folder holding a Frontmatter, a Body, and
optionally its Resources. Identified by its Skill Name.
_Avoid_: capability, module, plugin, tool

**Skill Name**:
The identity of a Skill, and the only handle a client uses to ask for one. Lower
case letters, digits and hyphens, at most 64 characters, never starting or
ending with a hyphen and never carrying two in a row. Always equal to the name
of its Skill Directory.
_Avoid_: id, slug, key, title

**Skill Directory**:
The folder that is a Skill. Its name is the Skill Name; it holds `SKILL.md` and
whatever Resources the Skill bundles.
_Avoid_: skill folder, package

**Skills Root**:
The single directory under which every Skill Directory sits. The whole library
the server exposes.
_Avoid_: library path, store, repo

**Frontmatter**:
The YAML block at the head of a `SKILL.md`, carrying a Skill's metadata. Two
fields are required, `name` and `description`; `license`, `compatibility`,
`metadata` and `allowed-tools` are optional; anything else is an undefined key.
_Avoid_: header, metadata block, preamble

**Undefined Key**:
A Frontmatter key the specification does not define. It never makes a Skill
invalid and it is never removed from what the client receives.
_Avoid_: unknown field, extra field, custom field

**Body**:
The Markdown that follows the Frontmatter in a `SKILL.md`: the instructions a
Skill exists to deliver. Never part of a Skill Summary.
_Avoid_: content, instructions, text, payload

**Skill Summary**:
The cheap projection of a Skill: its Skill Name and its description, and
nothing else. What Discovery returns.
_Avoid_: preview, stub, header, metadata

**Catalogue**:
The set of Valid Skills the server currently holds, one per Skill Name. Built
by reading the Skills Root; it holds Skill Summaries, not Bodies.
_Avoid_: index, registry, list, inventory

**Valid Skill**:
A Skill whose Frontmatter satisfies every rule of the specification, including
its `name` matching its Skill Directory. A Skill that is not valid is absent
from the Catalogue and indistinguishable from one that was never there.
_Avoid_: verified, checked, parsed, well-formed

**Resource**:
A file bundled inside a Skill Directory alongside `SKILL.md` — conventionally
under `scripts/`, `references/` or `assets/`, though a Skill may bundle any
file. Reached only through its Resource Path.
_Avoid_: asset, attachment, artifact, file

**Resource Path**:
Where a Resource sits relative to the root of its own Skill Directory. Never
absolute, and never denotes anything outside that Skill Directory.
_Avoid_: file path, location, uri

**Progressive Disclosure**:
The rule that a Skill is revealed in three widening steps — Skill Summary, then
Body, then Resources — each one loaded only when actually asked for. The reason
Discovery exists as a separate step rather than as a smaller Activation.
_Avoid_: lazy loading, pagination

**Discovery**:
Asking the Catalogue what Skills exist. Returns Skill Summaries.
_Avoid_: listing, search, browse

**Activation**:
Asking for one Skill's full `SKILL.md`, Frontmatter and Body together, exactly
as it sits on disk.
_Avoid_: fetch, load, open

**Token**:
The bearer credential a client presents. In this version every Token grants the
same thing: the whole Catalogue.
_Avoid_: key, secret, credential, apikey
