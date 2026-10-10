"""Field-level cleaning and validation for patient demographics.

Each method accepts loosely formatted input (a voice transcript is messy), returns the
canonical stored form, and raises ValueError with a plain-English reason otherwise.
"""

import re
from datetime import date, datetime

from app.interfaces.utilities import IClock, IFieldNormalizer
from app.models.enums import Sex


class FieldNormalizer(IFieldNormalizer):
    _CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
    # Letters (any alphabet) separated by single hyphens, apostrophes or spaces.
    # Spaces go beyond the brief's "alphabetic + hyphens/apostrophes" on purpose:
    # rejecting "De La Cruz" or "Mary Ann" would be wrong for real callers.
    _NAME = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")
    _EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$")
    _ZIP = re.compile(r"^\d{5}(-\d{4})?$")
    _DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y")
    _EARLIEST_BIRTH_YEAR = 1900

    _SEX_ALIASES = {
        "male": Sex.MALE,
        "m": Sex.MALE,
        "man": Sex.MALE,
        "female": Sex.FEMALE,
        "f": Sex.FEMALE,
        "woman": Sex.FEMALE,
        "other": Sex.OTHER,
        "decline to answer": Sex.DECLINE_TO_ANSWER,
        "decline": Sex.DECLINE_TO_ANSWER,
        "prefer not to say": Sex.DECLINE_TO_ANSWER,
    }

    _STATES = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
        "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
        "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
        "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
        "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
        "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
        "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
        "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
        "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
        "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
        "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
        "PR": "Puerto Rico", "GU": "Guam", "VI": "Virgin Islands", "AS": "American Samoa",
        "MP": "Northern Mariana Islands",
    }
    _STATE_BY_NAME = {name.lower(): code for code, name in _STATES.items()}

    def __init__(self, clock: IClock) -> None:
        self._clock = clock

    def clean_text(self, value: object) -> object:
        """Basic input sanitisation: drop control characters, collapse whitespace, and
        treat an empty string as 'not provided'. Non-strings pass through untouched."""
        if not isinstance(value, str):
            return value
        value = self._CONTROL_CHARS.sub(" ", value)
        value = " ".join(value.split())
        return value or None

    def name(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        value = value.replace("’", "'")
        if len(value) > 50:
            raise ValueError("must be 50 characters or fewer")
        if not self._NAME.match(value):
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
        if value.year < self._EARLIEST_BIRTH_YEAR:
            raise ValueError(f"year must be {self._EARLIEST_BIRTH_YEAR} or later")
        return value

    def sex(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        match = self._SEX_ALIASES.get(value.lower())
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
        if len(value) > 254 or not self._EMAIL.match(value):
            raise ValueError("must be a valid email address, like name@example.com")
        return value

    def state(self, value: object) -> str | None:
        value = self._text_or_none(value)
        if value is None:
            return None
        if value.upper() in self._STATES:
            return value.upper()
        # Callers say "Texas", not "T X"; accept the full name and store the abbreviation.
        code = self._STATE_BY_NAME.get(value.lower())
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
        if not self._ZIP.match(value):
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
        for date_format in self._DATE_FORMATS:
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        raise ValueError("must be a real calendar date in MM/DD/YYYY format")
