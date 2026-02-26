# api.civicpatch.org — Agent Instructions

## Overview
FastAPI backend service that handles job artifacts, storage, and GitHub workflow triggers.

## Tech Stack
- Python 3.x
- FastAPI
- Google Sheets (for cost tracking)
- AWS S3 (storage)
- GitHub Actions (workflow triggers)

## Key Paths
- `src/job_service/people_collector.py` — Handles artifact submission and processing
- `src/services/` — External service integrations (storage, GitHub, Google Sheets)
- `src/schemas/` — Pydantic request/response models
- `src/utils/file_utils.py` — File handling utilities

## Artifact Processing Flow
1. Receive ZIP upload with collected data
2. Extract and validate against expected patterns
3. Upload debug files to storage
4. Process images and update data with CDN URLs
5. Trigger GitHub data intake workflow
6. Track costs in Google Sheets

## File Patterns
**Artifact files** (zipped for GitHub):
- `data/*/local/*.yml`
- `data_source/*/local/*/workflow_context.json`

**Debug files** (uploaded to storage):
- `data_source/*/local/*/cache/*`
- `data_source/*/local/*/images/*`
- `data_source/*/local/*/costs.json`
- `data_source/*/local/*/workflow.log`

## Conventions
- Use `background_tasks` for non-blocking operations (e.g., cost tracking)
- Presigned URLs for S3 uploads
- Request IDs used for file organization in storage
