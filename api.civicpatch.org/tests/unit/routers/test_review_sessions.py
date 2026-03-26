import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from psycopg.errors import UniqueViolation

