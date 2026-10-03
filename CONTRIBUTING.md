# Contributing

## Development setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/check.sh              # format check, lint, mypy --strict, tests
python scripts/run_examples.py
```

Before committing: `ruff check --fix . && ruff format .` then `scripts/check.sh`.

## Pull requests

- One logical change per PR, with tests. Every feature needs tests; property-based
  tests (Hypothesis) are welcome for invariants.
- Use conventional commit messages (`feat:`, `fix:`, `perf:`, `docs:`, `test:`, `ci:`).
- Keep the core free of network calls, API keys and heavy dependencies; optional
  integrations go behind extras.

## Mechanism and policy contributions

- Must be deterministic functions of their inputs and serialisable via `to_spec()`
  (replay depends on both).
- Document rules, payments, assumptions and limitations in `docs/mechanisms.md`.
- Do not claim truthfulness, efficiency or optimality unless the documentation
  states the exact assumptions under which it holds for *this* implementation.

## Research and benchmark contributions

- Experiments must be YAML configs with a stated hypothesis and seed.
- Commit generated reports only from a clean working tree, and keep conclusions
  within what the report shows. Never edit benchmark or result numbers by hand.

## Architecture changes

Open an issue first for changes to core models, the auction state machine, event
schemas or the storage schema (which needs a new migration, never an edited one).

## Security

See [SECURITY.md](SECURITY.md); report vulnerabilities privately.
