MAP ?= maps/challenger/01_the_impossible_dream.txt

install:
	@uv sync --all-groups

run:
	@uv run fly-in ${MAP}

gui:
	@uv run fly-in -gui ${MAP}

debug:
	@uv run -m pdb -m fly-in

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov

lint:
	@uv run -m mypy ./src --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
	@uv run -m flake8 src

lint-strict:
	@uv run -m mypy ./src --strict
	@uv run -m flake8 src

.PHONY: install run debug clean lint lint-strict gui
