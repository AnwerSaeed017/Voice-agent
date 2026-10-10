from datetime import date, datetime, timezone

from app.interfaces.utilities import IClock


class UtcClock(IClock):
    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self) -> date:
        return self.utc_now().date()
