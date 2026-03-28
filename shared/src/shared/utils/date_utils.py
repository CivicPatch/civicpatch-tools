from datetime import datetime, timezone

STREAK_TIMEZONE = "America/Los_Angeles"


def today_utc_isoformat() -> str:
    return datetime.now(timezone.utc).date().isoformat()
