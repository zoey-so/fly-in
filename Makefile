.PHONY: install run debug clean lint lint-strict

install:
	uv sync

run:
	uv run fly-in 

debug:
	uv run -m pdb -m fly-in

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov

lint:
	uv run -m mypy ./src --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
	uv run -m flake8 src

lint-strict:
	uv run -m mypy ./src --strict
	uv run -m flake8 src
