"""Runs the JavaScript unit tests (app/tests/frontend/unit/*.test.mjs) with Node's built-in
test runner, so `pytest` covers the front end as well. Needs Node 22 or later; skipped without it."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

UNIT_DIRECTORY = Path(__file__).resolve().parent / "unit"
ROOT = Path(__file__).resolve().parents[3]


def find_node() -> str | None:
    return os.getenv("NODE_PATH_EXECUTABLE") or shutil.which("node") or next(
        (str(path) for path in (Path("D:/nodejs/node.exe"), Path("C:/Program Files/nodejs/node.exe")) if path.exists()), None)


@pytest.mark.parametrize("test_file", sorted(UNIT_DIRECTORY.glob("*.test.mjs")), ids=lambda path: path.name)
def test_javascript_unit_tests(test_file):
    node = find_node()
    if node is None:
        pytest.skip("Node.js is not installed")
    result = subprocess.run([node, "--test", str(test_file)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
