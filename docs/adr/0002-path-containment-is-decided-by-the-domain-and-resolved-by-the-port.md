# ADR-0002 — Path containment is decided by the domain and resolved by the port

status: accepted
date: 2026-09-16
origin_feature: FEAT-001

## Context

INV-3 says every byte returned by a Resource read comes from a file inside that
Skill's own Skill Directory. Enforcing it needs a fact the domain cannot obtain:
whether a path, after following symlinks, still lands inside that directory.
Symlink resolution is I/O, and the core forbids I/O. Meanwhile the obvious
shortcut — refusing any path containing `..` — is not the rule at all: it passes
a symlink that points anywhere on the server, and it refuses paths that are
perfectly legitimate once normalised.

## Decision

Containment is split into three steps, and the domain owns the first and last.

1. **Syntactic refusal, in the domain.** A Resource Path cannot be constructed
   from an absolute path or an empty one. This is a constructor that rejects,
   not a check a caller may forget.
2. **Resolution, in the port.** Given a Skill Directory and a Resource Path, the
   adapter returns two resolved real locations — the Resource's and the Skill
   Directory's own — as opaque values. The adapter reports facts and decides
   nothing.
3. **Verdict, in the domain.** A pure function compares the two resolved values
   and answers whether the first lies within the second. Only an affirmative
   verdict permits the read.

The read is therefore a separate port operation from the resolution, and is only
ever reached after the domain has said yes.

## Alternatives rejected

- **Let the adapter decide containment**: rejected because it puts the security
  invariant in the layer with no unit tests and the most implementation variance,
  and because a second adapter would own a second copy of the rule. A rule that
  exists twice is a rule that will disagree with itself.
- **Refuse any path containing `..` and be done**: rejected because it is
  string matching standing in for a real check. It does not stop a symlink, which
  is the actual escape route, while refusing `references/../references/x.md`,
  which is harmless. It defends the spelling of the attack, not the attack.
- **One port operation that resolves, checks and reads**: rejected because it
  collapses the verdict back into the adapter — the domain would be trusting a
  boolean it did not compute, which is the same as not owning the invariant.
- **Refuse symlinks outright inside a Skill Directory**: rejected because it
  breaks legitimate library layouts and does not generalise; a Skill Directory
  that is itself reached through a symlink is normal, and would have to be
  special-cased anyway.

## Consequences

The invariant becomes testable without a filesystem: the verdict function takes
two resolved values and is exercised with pairs that are inside, outside,
identical, and adjacent-but-not-nested — the last being the case that catches a
naive string-prefix implementation, where `/skills/demo-evil` looks contained
in `/skills/demo` because the text starts the same way. The prefix comparison
must be path-segment aware, and that is a domain concern now.

Resolution and read being two separate port calls opens a window between them in
which a symlink could be repointed. At this scale, with a Skills Root curated by
hand and no client able to write, the window is accepted rather than closed;
closing it would mean resolving and reading through a single held file handle,
which is a real option if the threat model ever changes.

The cost is one extra round trip to the port per Resource read, and a port
surface that is wider than the obvious "read this file" — which will look like
over-engineering to a reader who has not read this ADR. That is what this ADR is
for.
