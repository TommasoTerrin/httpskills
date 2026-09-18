# ADR-0003 — The Token registry stays in the adapter, and the domain has no authorization concept

status: accepted
date: 2026-09-16
origin_feature: FEAT-001

## Context

Grilling settled that the server accepts several Tokens, read from the
environment, all granting the same thing, and recorded the intention of
"modelling it as a small registry so the future skillset map has a seat". It
also deferred skillsets out of this version entirely. Meanwhile fastmcp already
ships `StaticTokenVerifier`, which is exactly a set of Tokens checked against a
presented bearer value. So the question is not how to authenticate, it is where
the concept belongs.

## Decision

In this version the domain has no authorization concept at all. Authentication
is the adapter's, performed by `StaticTokenVerifier` over a set of Tokens read
from the environment. No domain type represents a Token, a principal or a grant.
A caller either fails at the transport and reaches nothing, or succeeds and the
domain answers as it would for any caller.

The seat kept for the future is a seam, not a class: the adapter is the only
component that knows who is calling, and the Catalogue is already a filtered
projection of the Skills Root. When skillsets arrive, the adapter passes the
granted skillset names inward and the Catalogue gains a filter. Nothing that
exists today has to move.

## Alternatives rejected

- **A `TokenRegistry` aggregate in the domain now**: rejected by the deletion
  test. Delete it and put the adapter's check back: no invariant reappears
  anywhere, because every Token grants identical access and the domain therefore
  never has a question to answer. It would be a pass-through that exists only to
  look ready for a feature that is explicitly out of scope.
- **Model an `AuthenticatedCaller` value object carrying an empty set of
  grants**: rejected for the same reason one level up — an object whose only
  field is always empty is a comment with a constructor. It also invites the
  worse mistake of writing tests that assert the empty set, which would have to
  be deleted the moment the feature it was anticipating actually arrives.
- **Write our own token verification in the domain to avoid depending on
  fastmcp's**: rejected because verification here is a set membership test; the
  library already does it, and reimplementing it buys purity in a place where no
  rule of ours lives.

## Consequences

The domain stays free of the one concept most likely to leak infrastructure into
it, and the auth surface in this version is a few lines of adapter wiring rather
than a layer.

The non-obvious effect is on the tests: there is no domain-level test of
authorization, because there is no authorization. AC-FEAT-001-024 through
AC-FEAT-001-026 are adapter tests against a running server, and they cannot be
pushed down into fast unit tests. That is correct rather than unfortunate —
a unit test of "every Token grants everything" asserts nothing.

The risk this accepts: when skillsets arrive, the temptation will be to keep
filtering in the adapter, because that is where the caller's identity already
is. That would put a rule about which Skills exist for whom outside the domain,
next to the transport. The filter belongs on the Catalogue. This paragraph is
the warning to the reader who gets there.
