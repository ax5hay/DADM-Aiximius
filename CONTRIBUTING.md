# Contributing to DADM-Aiximius

Thank you for your interest in contributing. This document outlines how to get your environment set up and how we handle patches.

## Code of conduct

Be respectful and professional. This project deals with defensive security and government deployment; accuracy and clarity matter.

## Getting started

- **Clone and read:** [README.md](README.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/RUNBOOK.md](docs/RUNBOOK.md).
- **Stack:** Rust (agent), Python 3.11+ (training, federated, graph, reasoning, mesh). Use a virtual environment for Python.
- **Formatting:**
  - Rust: `cargo fmt` and `cargo clippy` in `agent/`.
  - Python: We use [Ruff](https://docs.astral.sh/ruff/) and [EditorConfig](https://editorconfig.org); see [.editorconfig](.editorconfig).

## Running tests

- **Rust:** From repo root, `cargo test` in `agent/`.
- **Python:** From repo root, `pip install -r tests/requirements.txt` (and component requirements as needed), then:
  ```bash
  export PYTHONPATH="$PWD/federated:$PWD/graph:$PWD/reasoning:$PWD"
  pytest tests/unit -v
  ```
- **CI:** All GitHub Actions (Rust, Python, Lint, Docker build, Deploy verify) should pass.

## Submitting changes

1. **Branch:** Create a branch from `main` (or `master`). Use a short prefix, e.g. `fix/`, `feat/`, `docs/`.
2. **Commit:** Write clear, atomic commits. Reference issues/PRs where relevant.
3. **Pull request:** Open a PR against `main`/`master`. Fill in the PR template. Ensure CI is green.
4. **Review:** Address review feedback. Maintainers will merge when the PR is approved and CI passes.

## Scope

- **Agent (Rust):** Collectors, features, model inference, storage, risk engine, uplink. Keep dependencies minimal and cross-platform where possible.
- **Python services:** Follow existing patterns (Flask, env-based config). Add tests in `tests/unit/` for new behavior.
- **Docs:** Update README, RUNBOOK, or architecture docs when behavior or setup changes.
- **Security:** Do not add secrets or weaken verification (e.g. model signing, crypto). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## Questions

Open a [GitHub Discussion](https://github.com/Aiximius/DADM-Aiximius/discussions) or an issue for questions and design ideas.
