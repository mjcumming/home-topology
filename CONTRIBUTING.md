# Contributing to home-topology

Thank you for your interest in contributing to `home-topology`! This document provides guidelines and workflows for contributing.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Pull Request Process](#pull-request-process)
4. [Release Process](#release-process)
5. [Communication](#communication)

---

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git
- Basic understanding of Home Assistant (for integration development)

### Initial Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/yourusername/home-topology.git
   cd home-topology
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation**:
   ```bash
   pytest tests/ -v
   ```

### Project Structure

```
home-topology/
├── src/home_topology/      # Core library
│   ├── core/               # Kernel components
│   └── modules/            # Behavior modules
├── tests/                  # Test suite
├── examples/               # Usage examples
├── docs/                   # Additional documentation
├── DESIGN.md               # Architecture spec
├── CODING-STANDARDS.md     # Coding guidelines
└── pyproject.toml          # Package config
```

---

## Development Workflow

### 1. Choose a Task

- Check [Issues](https://github.com/yourusername/home-topology/issues) for open tasks
- Look for issues tagged `good first issue` or `help wanted`
- Discuss new features in an issue before implementing

### 2. Create a Branch

Branch naming:
- `feat/feature-name` - New features
- `fix/bug-description` - Bug fixes
- `docs/topic` - Documentation updates
- `refactor/component` - Code refactoring

```bash
git checkout develop
git pull origin develop
git checkout -b feat/adaptive-timeout
```

### 3. Make Changes

Follow [CODING-STANDARDS.md](./CODING-STANDARDS.md):
- Write type-hinted, documented code
- Add tests for new functionality
- Update relevant documentation

### 4. Run Checks Locally

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Run tests with coverage
pytest tests/ -v --cov=home_topology --cov-report=term-missing

# Run example to verify
PYTHONPATH=src python3 example.py
```

### 5. Commit Changes

Follow the commit message format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Example:
```bash
git add src/home_topology/modules/occupancy/module.py
git commit -m "feat(occupancy): add adaptive timeout mode

Implements learning-based timeout adjustment based on
historical occupancy patterns.

Closes #42"
```

### 6. Push and Create PR

```bash
git push origin feat/adaptive-timeout
```

Then create a Pull Request on GitHub targeting the `develop` branch.

---

## Pull Request Process

### PR Title Format

Use the same format as commit messages:
```
feat(occupancy): add adaptive timeout mode
fix(bus): prevent handler exceptions from crashing kernel
docs(design): clarify entity-location mapping rules
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Changes
- Added X
- Modified Y
- Fixed Z

## Testing
- [ ] Added unit tests
- [ ] Added integration tests
- [ ] Manually tested with example.py
- [ ] Updated documentation

## Related Issues
Closes #42
Related to #38

## Checklist
- [ ] Code follows CODING-STANDARDS.md
- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for significant changes)
```

### Review Process

1. **Automated Checks**: CI must pass (linting, typing, tests)
2. **Code Review**: Maintainer reviews code for:
   - Adherence to design principles
   - Code quality and readability
   - Test coverage
   - Documentation completeness
3. **Feedback**: Address review comments, push updates
4. **Approval**: Maintainer approves and merges

### Merge Strategy

- **Squash merge** to `develop` for feature branches
- **Merge commit** from `develop` to `main` for releases

---

## Release Process

`home-topology` follows **semantic versioning** (SemVer):

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes (e.g., 1.0.0 → 2.0.0)
- **MINOR**: New features, backward compatible (e.g., 1.2.0 → 1.3.0)
- **PATCH**: Bug fixes, backward compatible (e.g., 1.2.1 → 1.2.2)

### Release Workflow

#### 1. Prepare Release (Maintainer)

On `develop` branch:

```bash
# Update version in pyproject.toml
# Update CHANGELOG.md with release notes
# Commit changes
git add pyproject.toml CHANGELOG.md
git commit -m "chore: prepare release v1.3.0"
git push origin develop
```

#### 2. Create Release Branch

```bash
git checkout -b release/v1.3.0
git push origin release/v1.3.0
```

#### 3. Final Testing

- Run full test suite on release branch
- Test HA integration (if applicable)
- Verify documentation

#### 4. Merge to Main

```bash
git checkout main
git merge --no-ff release/v1.3.0 -m "Release v1.3.0"
git tag -a v1.3.0 -m "Release version 1.3.0"
git push origin main --tags
```

#### 5. Build and Publish (Automated via CI)

CI triggers on tag push:

```bash
# Build package
python -m build

# Publish to PyPI (automated)
twine upload dist/*
```

#### 6. Merge Back to Develop

```bash
git checkout develop
git merge main
git push origin develop
```

#### 7. GitHub Release

Create a release on GitHub:
- Tag: `v1.3.0`
- Title: `home-topology v1.3.0`
- Description: Copy from CHANGELOG.md

#### 8. Announce

- Post to Home Assistant forums
- Update documentation site
- Announce in Discord/community channels

### Release Schedule

- **Patch releases**: As needed for critical bugs
- **Minor releases**: Monthly (if features ready)
- **Major releases**: When breaking changes necessary

---

## Communication

### Reporting Issues

When reporting bugs, include:
- Home-topology version
- Python version
- Platform (HA version if applicable)
- Minimal reproduction steps
- Expected vs actual behavior
- Relevant logs

Template:
```markdown
**Version**: home-topology v1.2.3, Python 3.11
**Platform**: Home Assistant 2024.11

**Description**:
Brief description of the issue.

**Steps to Reproduce**:
1. Create location with...
2. Configure occupancy module...
3. Observe...

**Expected**: Occupancy should change to True
**Actual**: Occupancy remains False

**Logs**:
```
2025-11-24 10:00:00 ERROR ... 
```
```

### Feature Requests

Open an issue with:
- Use case / motivation
- Proposed solution
- Alternatives considered
- Implementation sketch (if applicable)

### Questions and Discussion

- **Issues**: For bugs, features, tasks
- **Discussions**: For questions, ideas, help
- **Discord**: For real-time chat (link TBD)

---

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Spam or off-topic posts

### Enforcement

Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

Report issues to: [maintainer email]

---

## Development Tips

### Running Specific Tests

```bash
# Single test file
pytest tests/test_bus.py -v

# Single test function
pytest tests/test_bus.py::test_event_bus_filtering -v

# Tests matching pattern
pytest -k "occupancy" -v
```

### Debugging

```bash
# Run with verbose logging
PYTHONPATH=src python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# your test code
"

# Run with pdb on failure
pytest tests/ --pdb
```

### Type Checking Specific Files

```bash
mypy src/home_topology/core/bus.py
```

### Coverage Reports

```bash
# Terminal report
pytest tests/ --cov=home_topology --cov-report=term-missing

# HTML report
pytest tests/ --cov=home_topology --cov-report=html
open htmlcov/index.html
```

### Documentation

Build and preview docs locally:
```bash
# If using sphinx or mkdocs (TBD)
mkdocs serve
```

---

## Advanced Topics

### Writing a Custom Module

See `examples/custom-module.py` for a template.

Key steps:
1. Subclass `LocationModule`
2. Implement required methods
3. Subscribe to events in `attach()`
4. Emit semantic events on state changes
5. Add tests

### Contributing to HA Integration

The HA integration lives in a separate repo: `home-topology-ha`

See that repo's CONTRIBUTING.md for specifics.

### Performance Testing

For performance-sensitive changes:

```bash
# Profile with cProfile
python3 -m cProfile -s cumtime example.py

# Memory profiling
pip install memory_profiler
python3 -m memory_profiler example.py
```

---

## Recognition

Contributors are recognized in:
- `AUTHORS.md` file
- Release notes
- GitHub contributors page

Significant contributions may earn you:
- Maintainer status
- Commit access
- Input on roadmap decisions

---

## License

By contributing, you agree that your contributions will be licensed under the project's license (MIT/Apache-2.0, TBD).

---

## Questions?

Open an issue or discussion - we're happy to help!

---

**Document Status**: Active  
**Last Updated**: 2025-11-24

