#!/usr/bin/env python3
"""Write one reproducible provenance record for a claim-bearing figure.

The public interface is intentionally small: callers provide the semantic
route, source/data/output paths, and plot-specific declarations. Hashing,
runtime discovery, path normalization, and stable record hashing stay inside
this module.
"""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

from project_paths import project_relative, resolve_project_path


def write_figure_provenance(
    root: Path,
    *,
    figure_id: str,
    claim_id: str,
    route: dict[str, Any],
    source_code: Path,
    input_data: Path,
    png: Path,
    pdf: Path,
    statistics: dict[str, Any],
    transformations: dict[str, Any],
    dpi: int,
    seed: int | None,
    warnings: list[str] | None = None,
    runtime: dict[str, Any] | None = None,
    source_artifacts: dict[str, Path] | None = None,
    export_artifacts: dict[str, Path] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Write and return the per-figure provenance record.

    record_sha256 hashes the canonical JSON payload before that field is
    appended. This avoids asking a JSON file to contain its own byte hash.
    """

    root = root.resolve()
    actual = {
        "backend": str(route.get("backend") or "").lower(),
        "library": str(route.get("library") or "").lower(),
    }
    recommended = route.get("recommended")
    if not isinstance(recommended, dict):
        recommended = {
            "backend": actual["backend"],
            "library": actual["library"],
            "route_id": route.get("route_id"),
        }

    source = {
        "source_code": artifact(root, source_code),
        "input_data": artifact(root, input_data),
    }
    for name, path in (source_artifacts or {}).items():
        if not name or name in source:
            raise ValueError(f"invalid or duplicate provenance source artifact: {name!r}")
        source[name] = artifact(root, path)

    export = {
        "dpi": int(dpi),
        "png": artifact(root, png),
        "pdf": artifact(root, pdf),
        "warnings": list(warnings or []),
    }
    for name, path in (export_artifacts or {}).items():
        if not name or name in export:
            raise ValueError(f"invalid or duplicate provenance export artifact: {name!r}")
        export[name] = artifact(root, path)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "figure_id": figure_id,
        "claim_id": claim_id,
        "route": {
            "route_id": route.get("route_id"),
            "route_mode": route.get("route_mode", "structured_confirmed"),
            "recommended": recommended,
            "actual": actual,
            "fallback": route.get("fallback"),
            "override": route.get("override"),
            "rationale": route.get("rationale", ""),
            "constraints": route.get("constraints", {}),
        },
        "source": source,
        "runtime": {**python_runtime(), **(runtime or {}), "seed": seed},
        "statistics": statistics,
        "transformations": transformations,
        "export": export,
    }
    payload["record_sha256"] = canonical_sha256(payload)
    stem = figure_id.removeprefix("fig_")
    path = root / "results" / "figures_data" / f"{stem}_provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, payload


def verify_record_sha256(payload: dict[str, Any]) -> bool:
    """Return whether a loaded provenance payload has its canonical hash."""

    expected = str(payload.get("record_sha256") or "")
    unsigned = {key: value for key, value in payload.items() if key != "record_sha256"}
    return len(expected) == 64 and expected == canonical_sha256(unsigned)


def artifact(root: Path, path: Path) -> dict[str, str]:
    resolved = resolve_project_path(root, path)
    if not resolved.is_file():
        raise FileNotFoundError(f"provenance artifact is missing: {resolved}")
    return {"path": project_relative(root, resolved), "sha256": sha256_file(resolved)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def python_runtime() -> dict[str, str]:
    import matplotlib

    try:
        import seaborn

        seaborn_version = seaborn.__version__
    except Exception:
        seaborn_version = "not_available"
    return {
        "python": platform.python_version(),
        "matplotlib": matplotlib.__version__,
        "seaborn": seaborn_version,
    }


def relative(root: Path, path: Path) -> str:
    return project_relative(root, path)
