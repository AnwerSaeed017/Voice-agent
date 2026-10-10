from pathlib import Path

from app.interfaces.utilities import ISqlLoader


class SqlFileLoader(ISqlLoader):
    """Loads raw SQL kept in app/sql so queries are not buried in Python strings."""

    _SQL_DIRECTORY = Path(__file__).resolve().parents[1] / "sql"

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def load(self, name: str) -> str:
        if name not in self._cache:
            self._cache[name] = (self._SQL_DIRECTORY / f"{name}.sql").read_text(encoding="utf-8")
        return self._cache[name]
