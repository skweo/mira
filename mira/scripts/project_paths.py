#!/usr/bin/env python3
"""Resolve project artifacts without allowing paths to escape the project root."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ProjectPathError(ValueError):
    """Raised when an artifact path is empty or outside the project root."""


def resolve_project_path(root: Path, value: Any) -> Path:
    """Return a resolved path inside *root* or raise ``ProjectPathError``."""

    project_root = Path(root).resolve()
    text = str(value or "").strip()
    if not text:
        raise ProjectPathError("project artifact path is empty")
    candidate = Path(text)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ProjectPathError(f"artifact is outside project root: {text}") from exc
    return resolved


def project_relative(root: Path, value: Any) -> str:
    """Return a normalized project-relative artifact path."""

    project_root = Path(root).resolve()
    return resolve_project_path(project_root, value).relative_to(project_root).as_posix()
