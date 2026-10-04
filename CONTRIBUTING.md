# Contributing to Agentic Support Copilot

Thank you for your interest in contributing!

## Development Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/Vineetiitg/Agentic-Support-Copilot.git
   cd Agentic-Support-Copilot
   ```
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Running Tests

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=app --cov-report=term-missing
```

## Code Quality

```bash
ruff check app/ tests/
ruff format app/ tests/
bandit -r app/ -s B101,B311
```

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(scope):` — New features
- `fix(scope):` — Bug fixes  
- `refactor(scope):` — Code restructuring
- `test(scope):` — Test changes
- `docs(scope):` — Documentation
- `chore(scope):` — Maintenance
