"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Business clock used to interpret relative dates such as
                "today" or "June 15" in intake conversations.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

# Timezone of the procurement business; "today" means today in this zone.
BUSINESS_TIMEZONE = ZoneInfo("Europe/Rome")

# A clock returns the current time. Extractors accept one so tests can fix
# the date instead of depending on the day they run.
Clock = Callable[[], datetime]


def business_now() -> datetime:
    """Return the current time in the business timezone."""

    return datetime.now(BUSINESS_TIMEZONE)
