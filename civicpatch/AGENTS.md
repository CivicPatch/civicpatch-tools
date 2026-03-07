# civicpatch — Agent Instructions

## Overview
Core Python package for collecting municipal official data via web scraping and LLM extraction.

## Tech Stack

### Backend
- Python 3.x
- LLM integration (OpenAI)
- Web scraping

### Frontend
- Lit HTML with Haunted hooks
- Entrypoint: `src/frontend/components`

## Frontend Components

- All frontend component files should be named using **kebab-case** (e.g., `progress-page.js`, `summary-stats.js`, `locality-gaps.js`).
- Component directories should also use **kebab-case**.
- Custom elements should be registered with kebab-case names (e.g., `<progress-page>`, `<summary-stats>`).
- This ensures consistency and compatibility with web component naming conventions.

## Key Paths
- `src/services/openai/prompts.py` — LLM prompts for data extraction
- `src/services/gemini_gemini/prompts.py` — LLM prompts for data extraction

## Conventions
- Async/await for I/O operations
- Use `config_utils` for designation/role configuration

## Tests
- pytest