.PHONY: install test run

install:
	pip install -e ".[dev]"

test:
	pytest -q

run:
	python -m access_review --as-of 2026-10-14
