# Dynasty Fantasy Football - Development Makefile
# Provides convenient commands for code quality, testing, and development tasks

.PHONY: help install test lint format type-check check fix clean all dev-setup import-data run

# Default target
help:
	@echo "Dynasty Fantasy Football - Available Commands:"
	@echo ""
	@echo "🔧 Development Setup:"
	@echo "  install      - Install dependencies using uv"
	@echo "  dev-setup    - Full development environment setup"
	@echo ""
	@echo "🧪 Testing & Quality:"
	@echo "  test         - Run all tests with pytest"
	@echo "  test-v       - Run tests with verbose output"
	@echo "  test-cov     - Run tests with coverage report"
	@echo ""
	@echo "🔍 Code Quality:"
	@echo "  lint         - Run ruff linting (read-only)"
	@echo "  format       - Format code with ruff"
	@echo "  type-check   - Run mypy type checking (via hatch)"
	@echo "  check        - Run all quality checks (lint + type-check)"
	@echo "  fix          - Auto-fix linting issues"
	@echo ""
	@echo "🚀 Application:"
	@echo "  run          - Start Streamlit development server"
	@echo "  import-data  - Import player rankings from external sources"
	@echo ""
	@echo "🧹 Utility:"
	@echo "  clean        - Clean up cache and temporary files"
	@echo "  all          - Run complete CI pipeline (install + check + test)"

# Installation and setup
install:
	@echo "📦 Installing dependencies..."
	uv sync

dev-setup: install
	@echo "🔧 Setting up development environment..."
	uv add --dev pytest
	@echo "ℹ️  Note: mypy and types are managed by hatch (run 'hatch run types:check')"
	@echo "✅ Development environment ready!"

# Testing
test:
	@echo "🧪 Running tests..."
	uv run pytest

test-v:
	@echo "🧪 Running tests with verbose output..."
	uv run pytest -v

test-cov:
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=dynasty --cov-report=term-missing

# Code quality
lint:
	@echo "🔍 Running ruff linting..."
	uv run ruff check

format:
	@echo "✨ Formatting code with ruff..."
	uv run ruff format

type-check:
	@echo "🔍 Running mypy type checking..."
	hatch run types:check

check: lint type-check
	@echo "✅ All code quality checks completed!"

fix:
	@echo "🔧 Auto-fixing linting issues..."
	uv run ruff check --fix
	uv run ruff format

# Application commands
run:
	@echo "🚀 Starting Streamlit development server..."
	uv run streamlit run home.py

import-data:
	@echo "📊 Importing player rankings from external sources..."
	uv run python -m dynasty.import

# Utility
clean:
	@echo "🧹 Cleaning up cache and temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name "*.coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup completed!"

# CI Pipeline
all: install check test
	@echo "🎉 Complete CI pipeline finished successfully!"

# Development workflow shortcuts
dev: fix test
	@echo "🎯 Development workflow completed!"

ci: all
	@echo "🤖 CI pipeline completed!"