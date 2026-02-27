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

## Key Paths
- `src/services/openai/prompts.py` — LLM prompts for data extraction
- `src/services/gemini_gemini/prompts.py` — LLM prompts for data extraction

## Conventions
- Async/await for I/O operations
- Use `config_utils` for designation/role configuration

## Tests
- pytest