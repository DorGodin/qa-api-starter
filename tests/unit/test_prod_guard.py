"""Enforced, not conventional: every public helper that writes must guard prod."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

FUNCTIONS_DIR = Path(__file__).resolve().parents[2] / "utils" / "functions"
READ_ONLY_HELPERS: set[str] = set()


def _public_functions(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            yield node


def _guards_prod(node) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring
        return (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and getattr(stmt.value.func, "id", None) == "assert_not_prod"
        )
    return False


@pytest.mark.parametrize("path", sorted(FUNCTIONS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_data_creating_helpers_guard_prod(path):
    if path.name == "__init__.py":
        pytest.skip("package marker")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    unguarded = [
        f.name for f in _public_functions(tree)
        if f.name not in READ_ONLY_HELPERS and not _guards_prod(f)
    ]
    assert not unguarded, (
        f"{path.name}: {unguarded} must call assert_not_prod('<name>') as the first statement, "
        "or be listed in READ_ONLY_HELPERS with a reason in the MR."
    )
