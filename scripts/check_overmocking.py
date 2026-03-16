#!/usr/bin/env python3
"""Check for over-mocking: test modules that import services/models but lack django_db tests.

Test modules that directly import from workflows.services or workflows.models
MUST have at least one test decorated with @pytest.mark.django_db to ensure
real DB integration is tested (not just mocked).

Usage:
    python scripts/check_overmocking.py
    python scripts/check_overmocking.py --strict  # exit code 1 on warnings

Returns exit code 0 on success, 1 on violations (with --strict).
"""

import ast
import sys
from pathlib import Path

TESTS_DIR = Path("tests")

# Imports that indicate the test module touches DB-backed code.
# Only include modules that directly query Django ORM models.
# Redis-only services (cache_manager, debounce, rate_limiter, cost_tracker)
# are intentionally excluded — they don't need @pytest.mark.django_db.
DB_IMPORTS = {
    "workflows.models",
    "workflows.services.config_service",
    "workflows.services.metrics",
    "workflows.services.alerting",
}

# Markers that indicate real DB usage
DB_MARKERS = {"django_db"}


def _has_db_import(tree: ast.Module) -> list[str]:
    """Return list of DB-related imports found in the module."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for prefix in DB_IMPORTS:
                if node.module.startswith(prefix):
                    found.append(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in DB_IMPORTS:
                    if alias.name.startswith(prefix):
                        found.append(alias.name)
    return found


def _has_db_marker(tree: ast.Module) -> bool:
    """Check if any test function/method has @pytest.mark.django_db."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if _is_django_db_decorator(decorator):
                    return True
        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                if _is_django_db_decorator(decorator):
                    return True
    return False


def _is_django_db_decorator(node: ast.expr) -> bool:
    """Check if a decorator is pytest.mark.django_db (any form)."""
    source = ast.dump(node)
    if "django_db" in source:
        return True
    return False


def check_overmocking() -> list[str]:
    """Scan test files and return list of warnings."""
    warnings = []

    for test_file in sorted(TESTS_DIR.rglob("test_*.py")):
        # Skip e2e and integration directories
        if "e2e" in test_file.parts or "integration" in test_file.parts:
            continue

        try:
            source = test_file.read_text()
            tree = ast.parse(source)
        except SyntaxError:
            continue

        db_imports = _has_db_import(tree)
        if not db_imports:
            continue

        has_marker = _has_db_marker(tree)
        if has_marker:
            continue

        # Also check for autouse fixture with django_db pattern
        if "django_db" in source:
            continue

        relative = test_file
        imports_str = ", ".join(sorted(set(db_imports)))
        warnings.append(
            f"  {relative}\n"
            f"    Imports: {imports_str}\n"
            f"    Missing: @pytest.mark.django_db on at least one test"
        )

    return warnings


def main() -> int:
    strict = "--strict" in sys.argv
    warnings = check_overmocking()

    if not warnings:
        print("check_overmocking: All test modules OK")
        return 0

    print(f"check_overmocking: {len(warnings)} module(s) may be over-mocking:\n")
    for w in warnings:
        print(w)
    print(
        "\nTest modules that import from workflows.services or workflows.models "
        "should have at least one @pytest.mark.django_db test."
    )

    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
