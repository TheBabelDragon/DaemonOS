# Contributing

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

## Branch policy

- Do not commit directly to `main`.
- Feature work lands on `feat/*` branches; open a PR against `main`.

## Testing expectations

- Add or update unit tests for lifecycle, auth, flash safeguards, and API behavior.
- Prefer the simulator; do not require physical hardware for CI.
- Clearly mark any hardware-dependent test as optional / skipped by default.

## Code style

- Python 3.11+, type hints encouraged.
- Ruff for lint/format.
- Prefer boring, well-supported dependencies.

## Security

- Never commit secrets, private keys, or production credentials.
- Destructive flash paths must remain opt-in.
- Document new trust-boundary crossings in `docs/SECURITY.md`.
