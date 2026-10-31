# ClaimGuard Agent Instructions

## Python Code Quality & Formatting
Run `ruff check --fix .` and `ruff format .` before finishing any Python task.
All Python code must adhere to Python 3.11+ type hints, clean imports, and zero undefined variables.

## Security & Vulnerability Scanning
After generating or changing code, run the Snyk code scan and dependency scan. Fix any high or critical issues, then rescan.
Keep all dependencies pinned and secure.

