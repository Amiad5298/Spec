# Claude Code - Project Guidelines (ai-platform)

## Build & Run Commands
- Install dependencies: `pip install -e .` or `pip install -r requirements.txt`
- Run the tool (Ingot): `python -m ingot` or `ingot` (if installed)
- Active Virtualenv: `source .venv/bin/activate`

## Quality Control (Testing & Linting)
- Run tests: `pytest`
- Run specific test: `pytest tests/test_file.py`
- Linting: `ruff check .`
- Type checking: `mypy .`
- Formatting: `ruff format .`

## Coding Style & Patterns
- **Language**: Python 3.10+ (using Type Hints for everything).
- **Architecture**: Domain-driven, optimized for Spec-Driven Development (SDD).
- **Backend Patterns**: Prefer explicit over implicit, use Pydantic for data validation.
- **Async**: Use `asyncio` where appropriate for AI agent calls.
- **Error Handling**: Custom exceptions defined in `ingot/utils/errors.py` (`IngotError` base class).

## Project Context
- This is a CLI tool named 'Ingot' designed to enhance the Spec-Driven Development (SDD) process for AI agents.
- It interacts with AI agents (Auggie, Claude Code, Cursor, Aider, Gemini, Codex) to automate development tasks.
