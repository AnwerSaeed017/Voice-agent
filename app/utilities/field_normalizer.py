"""Field-level cleaning and validation for patient demographics.

Each method accepts loosely formatted input (a voice transcript is messy), returns the
canonical stored form, and raises ValueError with a plain-English reason otherwise.
"""

import re
from datetime import date, datetime

from app.constants.constants import (
    CONTROL_CHARACTERS,
    DATE_FORMATS,
    EARLIEST_BIRTH_YEAR,
    EMAIL_PATTERN,
    NAME_PATTERN,
    SEX_ALIASES,
    US_STATES,
    US_STATE_BY_NAME,
    ZIP_CODE_PATTERN,
)
from app.interfaces.utilities import IClock, IFieldNormalizer
from app.models.enums import Sex


class FieldNormalizer(IFieldNormalizer):
    def __init__(self, clock: IClock) -> None:
        self._clock = clock

    def clean_text(self, value: object) -> object:
        """Basic input sanitisation: drop control characters, collapse whitespace, and
        treat an empty string as 'not provided'. Non-strings pass through untouched."""
        if not isinstance(value, str):
            return value
        value = CONTROL_CHARACTERS.sub(" ", value)
        value = " ".join(value.split())
        return value or None

    def name(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        value = value.replace("’", "'")
        if len(value) > 50:
            raise ValueError("must be 50 characters or fewer")
        if not NAME_PATTERN.match(value):
            raise ValueError("may contain only letters, hyphens and apostrophes")
        return value

    def date_of_birth(self, value: object) -> date | None:
        if isinstance(value, datetime):
            value = value.date()
        if not isinstance(value, date):
            value = self._text_or_none(value)
            if value is None:
                return None
            value = self._parse_date(value)
        if value > self._clock.today():
            raise ValueError("cannot be in the future")
        if value.year < EARLIEST_BIRTH_YEAR:
            raise ValueError(f"year must be {EARLIEST_BIRTH_YEAR} or later")
        return value

    def sex(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        match = SEX_ALIASES.get(value.lower())
        if match is None:
            options = ", ".join(option.value for option in Sex)
            raise ValueError(f"must be one of: {options}")
        return match.value

    def phone(self, value: object) -> str | None:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        value = self._text_or_none(value)
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError(f"must be a 10-digit U.S. phone number (received {len(digits)} digits)")
        return digits

    def email(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        value = value.lower()
        if len(value) > 254 or not EMAIL_PATTERN.match(value):
            raise ValueError("must be a valid email address, like name@example.com")
        return value

    def state(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        if value.upper() in US_STATES:
            return value.upper()
        # Callers say "Texas", not "T X"; accept the full name and store the abbreviation.
        code = US_STATE_BY_NAME.get(value.lower())
        if code is None:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return code

    def zip_code(self, value: object) -> str | None:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value).zfill(5)
        value = self._text_or_none(value)
        if value is None:
            return None
        value = value.replace(" ", "")
        if value.isdigit() and len(value) == 9:
            value = f"{value[:5]}-{value[5:]}"
        if not ZIP_CODE_PATTERN.match(value):
            raise ValueError("must be a 5-digit ZIP code or ZIP+4 (12345 or 12345-6789)")
        return value

    def member_id(self, value: object) -> str | None:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        value = self._text_or_none(value)
        if value is None:
            return None
        value = value.replace(" ", "").replace("-", "").upper()
        if not (value.isascii() and value.isalnum()):
            raise ValueError("may contain only letters and numbers")
        if len(value) > 50:
            raise ValueError("must be 50 characters or fewer")
        return value

    def _text_or_none(self, value: object) -> str | None:
        value = self.clean_text(value)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("must be text")
        return value

    def _parse_date(self, value: str) -> date:
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        raise ValueError("must be a real calendar date in MM/DD/YYYY format")
