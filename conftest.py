"""
Author: L. Saetta
Date Last Modified: 2026-10-24
License: MIT
Description:    Repository-wide pytest checks. Stops the run when a test file
                is executed with the code of another file, which happens
                when two test modules end up with the same module name.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fail the collection if a test runs code from a different file.

    Several services have test files with the same name. If they become
    modules with the same name (for example after adding ``__init__.py`` to
    a ``tests`` folder), pytest silently reuses the first one, so the other
    files' tests never run and the summary still reports success.

    Raises:
        pytest.UsageError: If an item's module was loaded from another file.
    """

    shadowed_files = sorted(
        {
            str(item.path)
            for item in items
            if isinstance(item, pytest.Function)
            and Path(item.module.__file__).resolve() != item.path.resolve()
        }
    )
    if shadowed_files:
        raise pytest.UsageError(
            "These test files were replaced by another module with the same "
            "name, so their tests would not run: " + ", ".join(shadowed_files)
        )
