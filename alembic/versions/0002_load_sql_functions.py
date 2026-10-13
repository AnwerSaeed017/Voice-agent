"""load the SQL functions the repositories call

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 23:40:00

The tables come from the models (0001). This revision then loads the functions kept in
app/sql/functions. The files use CREATE OR REPLACE, so when a function changes, add a new
revision that calls load_functions() again.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

FUNCTIONS_DIRECTORY = Path(__file__).resolve().parents[2] / "app" / "sql" / "functions"
# Order matters: call_logs.sql only needs the tables, patients.sql reads call_logs.
FUNCTION_FILES = ("call_logs", "patients")


def statements(name: str) -> list[str]:
    """Split a SQL file into statements. A semicolon inside a $$ body does not end one."""
    found, current, in_body = [], [], False
    for line in (FUNCTIONS_DIRECTORY / f"{name}.sql").read_text(encoding="utf-8").splitlines():
        if not current and (not line.strip() or line.lstrip().startswith("--")):
            continue
        current.append(line)
        if line.count("$$") % 2 == 1:
            in_body = not in_body
        if not in_body and line.rstrip().endswith(";"):
            found.append("\n".join(current))
            current = []
    return found


def load_functions() -> None:
    for name in FUNCTION_FILES:
        for statement in statements(name):
            op.execute(sa.text(statement))


def upgrade() -> None:
    load_functions()


def downgrade() -> None:
    for statement in statements("drop"):
        op.execute(sa.text(statement))
