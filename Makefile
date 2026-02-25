# DADM-Aiximius — common tasks (GNU Make)
# Run from repo root.

.PHONY: help test test-rust test-python fmt lint docker-up docker-down

help:
	@echo "DADM-Aiximius targets:"
	@echo "  make test         - Run Rust + Python tests"
	@echo "  make test-rust    - Run agent tests (cargo test)"
	@echo "  make test-python  - Run unit tests (pytest tests/unit)"
	@echo "  make fmt          - Format Rust and check Python"
	@echo "  make lint         - Run Ruff and YAML check"
	@echo "  make docker-up    - Start stack (docker compose up -d)"
	@echo "  make docker-down  - Stop stack (docker compose down)"

test: test-rust test-python

test-rust:
	cd agent && cargo test

test-python:
	PYTHONPATH=$$(pwd)/federated:$$(pwd)/graph:$$(pwd)/reasoning:$$(pwd) pytest tests/unit -v --tb=short

fmt:
	cd agent && cargo fmt
	@echo "Python: use ruff format or editor formatter; see .editorconfig"

lint:
	ruff check . --config pyproject.toml 2>/dev/null || true
	python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); yaml.safe_load(open('mesh/openapi.yaml')); print('YAML OK')"

docker-up:
	docker compose up -d

docker-down:
	docker compose down
