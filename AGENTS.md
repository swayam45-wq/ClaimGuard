# ClaimGuard Agent Instructions

These instructions govern all code generation, refactoring, and maintenance across ClaimGuard.

---

## 1. Code Quality & Formatting (Ruff + SIM)
- Run `python -m ruff check --fix .` and `python -m ruff format .` before finishing any Python task.
- Adhere to `pyproject.toml` configurations (including `SIM` flake8-simplify rules for auto-simplifying nested logic and redundant constructs).
- Use strict Python 3.11+ type hints across all function signatures and data structures.
- Use strict TypeScript (`noImplicitAny`, no `any`) for frontend code.

---

## 2. Security & Vulnerability Scanning (Snyk)
- After generating or modifying code or dependencies, run `snyk test` on project manifests.
- Fix any high or critical severity CVEs immediately, then rescan.
- Keep all dependency versions pinned and secure.

---

## 3. Senior Engineer Review Pass
After completing any coding task, execute a senior-engineer review pass before finishing:
1. **Deduplication**: Find duplicated logic and extract it into shared helpers or utilities.
2. **Modularization**: Split any file over ~300 lines by responsibility (one primary concern per file).
3. **Simplification**: Simplify verbose constructs where fewer lines do the same job without hurting readability.
4. **Pruning**: Remove dead code, redundant comments, and unused abstractions.
5. **Transparency**: Always summarize what you changed in the review pass in your final response.

---

## 4. Git Hygiene
- Stage and commit changes after every self-contained milestone or review pass with clear conventional commits (`feat`, `fix`, `refactor`, `chore`, `docs`).
- Ensure `git status` reports a clean working tree before completing your turn.
