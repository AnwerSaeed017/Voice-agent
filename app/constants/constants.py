"""Fixed values shared across the application. Nothing here is read from the environment;
configurable values belong in app/core/config.py."""

import re
from datetime import timedelta
from pathlib import Path

from app.models.enums import Sex

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIRECTORY = Path(__file__).resolve().parents[1]
# Local secrets live in env/.env (git-ignored). In production the host injects real
# environment variables, which always win over the file.
ENV_FILE = APP_DIRECTORY.parent / "env" / ".env"
SQL_DIRECTORY = APP_DIRECTORY / "sql"
STATIC_DIRECTORY = APP_DIRECTORY / "static"
DASHBOARD_FILE = STATIC_DIRECTORY / "dashboard.html"

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
# The console loads only its own scripts and styles, so nothing injected can run or call out.
DASHBOARD_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
# Error codes for framework-raised HTTP errors; anything else is reported as "http_error".
HTTP_ERROR_CODES = {404: "not_found", 405: "method_not_allowed"}

# ---------------------------------------------------------------------------
# Validation error formatting (Pydantic error dictionaries)
# ---------------------------------------------------------------------------
ERROR_LOCATION_PREFIXES = {"body", "query", "path", "header"}
REQUIRED_ERROR_TYPES = {"missing", "string_type", "date_type"}
VALUE_ERROR_PREFIX = "Value error, "

# ---------------------------------------------------------------------------
# Patient field rules
# ---------------------------------------------------------------------------
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
# Letters (any alphabet) separated by single hyphens, apostrophes or spaces.
# Spaces go beyond the brief's "alphabetic + hyphens/apostrophes" on purpose:
# rejecting "De La Cruz" or "Mary Ann" would be wrong for real callers.
NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$")
ZIP_CODE_PATTERN = re.compile(r"^\d{5}(-\d{4})?$")
DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y")
EARLIEST_BIRTH_YEAR = 1900

SEX_ALIASES = {
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

US_STATES = {
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
US_STATE_BY_NAME = {name.lower(): code for code, name in US_STATES.items()}

# Set by the server, never by the client. They are dropped from input (rather than
# rejected as unknown) so a record fetched with GET can be edited and sent back with PUT.
SERVER_MANAGED_FIELDS = ("patient_id", "created_at", "updated_at", "deleted_at")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Function and argument names are interpolated into the call statement, so they must match this.
SQL_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

# Call log columns a caller may set through CallLogRepository.upsert. Each maps to a
# p_<name> argument of the call_log_upsert SQL function.
UPSERT_FIELDS = (
    "patient_id",
    "caller_number",
    "ended_reason",
    "summary",
    "transcript",
    "collected_payload",
)

# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------
# Window for the console's "new in the last 7 days" figure.
WEEK = timedelta(days=7)

# ---------------------------------------------------------------------------
# Vapi
# ---------------------------------------------------------------------------
VAPI_BASE_URL = "https://api.vapi.ai"
ASSISTANT_NAME = "Patient Registration Agent"
# Vapi's reply when a requested area code has no numbers left, e.g.
# "This area code is currently not available. Hint: Try one of 864, 689, 572."
AREA_CODE_HINT = re.compile(r"Try one of (\d{3})")

# ---------------------------------------------------------------------------
# Demo data: two clearly fictional patients inserted on first start
# ---------------------------------------------------------------------------
DEMO_PATIENTS = (
    {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "04/12/1988",
        "sex": "Female",
        "phone_number": "2025550143",
        "email": "jane.doe@example.com",
        "address_line_1": "123 Main Street",
        "address_line_2": "Apt 4B",
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62704",
        "insurance_provider": "Blue Cross Blue Shield",
        "insurance_member_id": "XYZ123456789",
        "emergency_contact_name": "John Doe",
        "emergency_contact_phone": "2025550144",
    },
    {
        "first_name": "Miguel",
        "last_name": "O'Connor-Reyes",
        "date_of_birth": "11/03/1975",
        "sex": "Male",
        "phone_number": "2025550178",
        "address_line_1": "78 Alameda Avenue",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701-4321",
        "preferred_language": "Spanish",
    },
)
