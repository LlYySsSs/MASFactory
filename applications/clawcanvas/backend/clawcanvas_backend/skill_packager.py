from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import CanvasDocument


def build_skill_package(
    document: CanvasDocument,
    *,
    run_output: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "manifest": asdict(document.manifest),
        "workflow": document.to_dict(),
        "runtime": {
            "supported_node_types": ["start", "agent", "end"],
            "warnings": list(warnings or []),
        },
        "last_run": run_output or {},
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def export_skill_package(
    document: CanvasDocument,
    *,
    export_root: str | Path,
    run_output: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    package = build_skill_package(document, run_output=run_output, warnings=warnings)
    export_dir = Path(export_root) / _package_dir_name(document.manifest.name)
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = export_dir / "skill.manifest.json"
    workflow_path = export_dir / "workflow.canvas.json"
    package_path = export_dir / "skill.package.json"

    manifest_path.write_text(
        json.dumps(package["manifest"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    workflow_path.write_text(
        json.dumps(package["workflow"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "export_dir": str(export_dir),
        "manifest_path": str(manifest_path),
        "workflow_path": str(workflow_path),
        "package_path": str(package_path),
        "package": package,
    }


def _package_dir_name(skill_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in skill_name)
    return f"{safe or 'clawcanvas_skill'}_{timestamp}"
