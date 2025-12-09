# Makefile for home-topology development

.PHONY: help install dev-install test test-verbose test-cov lint format typecheck clean example all check

# Default target
help:
	@echo "home-topology Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install package in editable mode"
	@echo "  make dev-install   Install with development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make format        Format code with black"
	@echo "  make lint          Run ruff linter"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make test          Run test suite"
	@echo "  make test-verbose  Run tests with verbose output"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make example       Run example script"
	@echo ""
	@echo "Quality:"
	@echo "  make check         Run all checks (format, lint, typecheck, test)"
	@echo "  make all           Same as 'make check'"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove build artifacts and cache"

# Installation
install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

# Testing
test:
	PYTHONPATH=src pytest tests/

test-verbose:
	PYTHONPATH=src pytest tests/ -v

test-cov:
	PYTHONPATH=src pytest tests/ -v --cov=home_topology --cov-report=term-missing

test-cov-html:
	PYTHONPATH=src pytest tests/ --cov=home_topology --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Code quality
format:
	black src/ tests/ example.py

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

# Run examples
example:
	PYTHONPATH=src python3 example.py

example-presence:
	PYTHONPATH=src python3 examples/presence-example.py

examples: example example-presence

# Combined checks
check: format lint typecheck test
	@echo ""
	@echo "✅ All checks passed!"

all: check

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Build package
build: clean
	python3 -m build

# Pre-commit hook simulation
pre-commit: format lint typecheck test check-dates
	@echo ""
	@echo "✅ Ready to commit!"

# Check for date errors in docs
check-dates:
	@./scripts/check-dates.sh

