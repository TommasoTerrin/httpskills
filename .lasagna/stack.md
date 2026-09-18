# Stack profile — httpskills

MCP HTTP server (fastmcp) exposing a centralised Agent Skills library.
Key reference: `base.md`.

language: python
runtime: cpython-3.12
package_manager: uv

## Commands

Verified at init: pytest 9.1.1, mypy strict and ruff all run clean on the
empty skeleton. `uv sync --extra dev` may need `UV_LINK_MODE=copy` on this
machine — the default hardlink mode hit a Windows trampoline error once.

test_command: uv run pytest
test_command_pattern: (pytest|uv run pytest|python -m pytest)
typecheck_command: uv run mypy src
lint_command: uv run ruff check
mutation_command: uv run mutmut run --paths-to-mutate src/httpskills/domain

## Test outcome classification

fail_compile_pattern: (ModuleNotFoundError|ImportError|SyntaxError|NameError|AttributeError:.*has no attribute)
fail_assert_pattern: (AssertionError|^E +assert|Failed: )
fail_generic_pattern: ([0-9]+ failed|[0-9]+ error|FAILED|ERROR)
pass_pattern: ([0-9]+ passed|OK|no tests ran)

## Paths

test_path: tests/
test_file_pattern: (^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$

core_path: src/httpskills/domain/
core_path: src/httpskills/ports/

## Layering rules

Import prefixes allowed inside the core. Everything else is a violation. List
internal modules and the pure third-party dependencies you accept — add
`pydantic` here if you use it for value objects, its validation is pure.

core_allowed_import: httpskills.domain
core_allowed_import: httpskills.ports
core_allowed_import: dataclasses
core_allowed_import: decimal
core_allowed_import: enum
core_allowed_import: typing
core_allowed_import: abc
core_allowed_import: collections
core_allowed_import: uuid
core_allowed_import: yaml

Patterns that make the core impure: I/O, clock, randomness, environment.

core_forbidden_pattern: datetime\.now|datetime\.utcnow|time\.time|time\.monotonic
core_forbidden_pattern: random\.|secrets\.|uuid4\(\)
core_forbidden_pattern: \bopen\(|Path\(.*\)\.(read|write)|os\.environ|os\.getenv
core_forbidden_pattern: requests\.|httpx\.|urllib|socket\.
core_forbidden_pattern: print\(|logging\.

## Project layout

Change these if the project already uses these paths for something else.

adr_dir: docs/adr
context_file: CONTEXT.md

## Budget and closing

budget_domain: 3
budget_adapter: 5
git_host: github
issue_cli: gh
bugfix_automerge: false

## Guardrails to switch off

Empty means all active. Names: block-tests, onion, test-result, budget,
precompact, session-status.

hooks_disabled:
