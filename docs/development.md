---
description: >-
  Developing AuctionSI: environment setup, the quality gate, the Python and
  dashboard test suites, PostgreSQL tests, docs builds, research and benchmark
  regeneration, CI and the release process.
---

# Development

## Setup

```bash
git clone https://github.com/Yashjindal11/auctionsi && cd auctionsi
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # tests, lint, types, API and PostgreSQL drivers
```

Python 3.11, 3.12 and 3.13 are supported and tested.

## Quality gate

```bash
.venv/bin/ruff check --fix . && .venv/bin/ruff format .
scripts/check.sh                      # format check, ruff, mypy --strict, pytest
```

`scripts/check.sh` runs exactly what CI runs for Python. Extra arguments go to
pytest (`scripts/check.sh -k replay`).

## Tests

| suite | where | run |
|---|---|---|
| Python unit, property (Hypothesis) and integration tests | `tests/` | `.venv/bin/pytest` |
| Only integration tests | `tests/` (`@pytest.mark.integration`) | `pytest -m integration` |
| Coverage (CI requires 93%) | | `pytest --cov --cov-report=term-missing` |
| Every `python` block in `README.md` and `docs/*.md` | `tests/docs/` | part of `pytest` |
| Examples | `examples/` | `python scripts/run_examples.py` |
| Dashboard (Vitest, Testing Library, jsdom) | `web/tests/` | `cd web && npm ci && npm test` |

Tests are grouped by package (`tests/market`, `tests/mechanisms`, `tests/api`, ...).
`tests/conftest.py` provides `ScriptedAgent` (a deterministic agent with a
configurable bid and behaviour), `task()` and the `market_factory` fixture (a
marketplace with a manual clock and fixed ids).

### PostgreSQL

The storage tests in `tests/storage/test_backends.py` run against every backend.
PostgreSQL runs when `AUCTIONSI_TEST_POSTGRES` points to a disposable database
(its tables are dropped first):

```bash
initdb -D /tmp/aucpg -U auctionsi --auth=trust
pg_ctl -D /tmp/aucpg -o "-p 54329 -k /tmp" start
createdb -h localhost -p 54329 -U auctionsi auctionsi_test
AUCTIONSI_TEST_POSTGRES=postgresql://auctionsi@localhost:54329/auctionsi_test scripts/check.sh
pg_ctl -D /tmp/aucpg stop && rm -rf /tmp/aucpg
```

CI runs the full suite against a PostgreSQL 17 service container.

## Dashboard

```bash
cd web
npm ci
npm run dev        # Vite on :5180, proxying /api (and the WebSocket) to :8000
npm test           # Vitest
npm run build      # type check, then write assets to src/auctionsi/api/static
```

The built assets are not committed (`.gitignore`); CI and the release workflows
build them before `python -m build`, and the wheel includes them.

## Documentation site

```bash
.venv/bin/pip install -e ".[docs]"
.venv/bin/mkdocs serve            # http://127.0.0.1:8000
.venv/bin/mkdocs build            # strict: broken links and missing pages fail
```

`scripts/mkdocs_hooks.py` publishes `CHANGELOG.md`, `SECURITY.md`,
`CONTRIBUTING.md`, `benchmarks/README.md`, `research/README.md` and every
`research/results/*/report.md` on the site and rewrites relative links, so the same
Markdown works on GitHub and on the site. `docs/overrides/main.html` adds Open
Graph, Twitter and JSON-LD metadata; each page's `description` front matter becomes
its meta description. The `Docs` workflow deploys to GitHub Pages on pushes to
`main` that touch the docs.

## Research and benchmarks

```bash
python research/run_all.py                 # every experiment (several minutes)
python research/run_all.py mechanisms      # one
python benchmarks/run_benchmarks.py --all
```

Commit regenerated results only from a clean working tree: manifests record the git
commit and mark it `+dirty` when tracked files have uncommitted changes. Never edit
result or benchmark numbers by hand; update the prose in `research/README.md` and
`benchmarks/README.md` from the generated files.

## Continuous integration

`.github/workflows/ci.yml` on every push and pull request:

- **lint**: ruff format check, ruff, mypy `--strict`
- **test**: Python 3.11/3.12/3.13 on Ubuntu, 3.12 on macOS and Windows; unit,
  integration and docs tests, then the examples
- **coverage-and-postgres**: the full suite against PostgreSQL with the coverage gate
- **web**: dashboard tests, type check and build
- **build**: builds the dashboard and the wheel, installs it in a clean virtualenv
  and smoke-tests the CLI and the bundled dashboard

## Releasing

1. Update `src/auctionsi/_version.py` and `web/package.json`, and move the
   `[Unreleased]` section of `CHANGELOG.md` under the new version.
2. Commit, push, and wait for CI to pass.
3. `git tag -a vX.Y.Z -m "AuctionSI X.Y.Z" && git push origin vX.Y.Z`.

`release.yml` runs the tests, builds the dashboard and the distributions, checks
that the version matches the tag and creates the GitHub release. If the repository
variable `PYPI_PUBLISH` is `true` it then triggers `publish.yml`, which uploads to
PyPI with trusted publishing (environment `pypi`, no API token).
