# Contributing to home-topology

Thanks for contributing to `home-topology`.

## Prerequisites

- Python 3.12+
- Git

## Local Setup

```bash
git clone https://github.com/mjcumming/home-topology.git
cd home-topology
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Development Workflow

1. Create a branch from `main`.
2. Make your changes with tests.
3. Run local checks.
4. Open a PR to `main`.

### Branch naming

- `feat/<topic>`
- `fix/<topic>`
- `docs/<topic>`
- `chore/<topic>`

## Required Local Checks

Run all checks before opening a PR:

```bash
black --check src/ tests/
ruff check src/ tests/
mypy src/
pytest tests/ --cov=home_topology --cov-report=term --cov-report=xml
```

Or run the helper target:

```bash
make check
```

## Pull Request Expectations

- Keep changes scoped.
- Add or update tests for behavior changes.
- Update docs for API or contract changes.
- Update `CHANGELOG.md` for user-visible changes.

## Release Process (Maintainers)

`home-topology` publishes from Git tags through GitHub Actions trusted publishing.

1. Update version in `pyproject.toml`.
2. Add release notes under that exact version in `CHANGELOG.md`.
3. Commit and push to `main`.
4. Create and push a matching tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Notes:
- Tag value after `v` must match `project.version` exactly.
- Publishing is handled by `.github/workflows/release.yml`.

## Scope Boundary

This repo is the platform-agnostic kernel.

- In scope: topology core, modules, tests, and library docs.
- Out of scope: Home Assistant adapter implementation details and frontend panel code.

Topomation is the active Home Assistant integration that consumes this library.
