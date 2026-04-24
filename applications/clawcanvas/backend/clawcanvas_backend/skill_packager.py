from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .schema import CanvasDocument


ExportFormat = Literal["json", "markdown", "zip"]


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
            "supported_node_types": ["start", "agent", "custom", "loop", "end"],
            "warnings": list(warnings or []),
            "engine": "MASFactory",
            "application": "ClawCanvas",
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
    format: ExportFormat = "json",
) -> dict[str, Any]:
    package = build_skill_package(document, run_output=run_output, warnings=warnings)
    export_dir = Path(export_root) / _package_dir_name(document.manifest.name or document.name)
    export_dir.mkdir(parents=True, exist_ok=True)

    if format == "markdown":
        return _export_as_markdown(document, package, export_dir)
    elif format == "zip":
        return _export_as_zip(document, package, export_dir)
    else:
        return _export_as_json(package, export_dir)


def _package_dir_name(skill_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = _official_skill_slug(skill_name)
    return f"{safe}_{timestamp}"


def _export_as_json(package: dict[str, Any], export_dir: Path) -> dict[str, Any]:
    paths = _write_publishable_skill_files(package, export_dir)

    return {
        "export_dir": str(export_dir),
        "format": "json",
        **{key: str(value) for key, value in paths.items()},
        "package": package,
    }


def _export_as_markdown(document: CanvasDocument, package: dict[str, Any], export_dir: Path) -> dict[str, Any]:
    paths = _write_publishable_skill_files(package, export_dir)

    return {
        "export_dir": str(export_dir),
        "format": "markdown",
        **{key: str(value) for key, value in paths.items()},
        "package": package,
    }


def _export_as_zip(document: CanvasDocument, package: dict[str, Any], export_dir: Path) -> dict[str, Any]:
    paths = _write_publishable_skill_files(package, export_dir)

    # Create ZIP file
    zip_path = export_dir.parent / f"{export_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in paths.values():
            zipf.write(file_path, file_path.name)

    return {
        "export_dir": str(export_dir),
        "format": "zip",
        "zip_path": str(zip_path),
        **{key: str(value) for key, value in paths.items()},
        "package": package,
    }


def _write_publishable_skill_files(package: dict[str, Any], export_dir: Path) -> dict[str, Path]:
    document = package["workflow"]
    manifest = package["manifest"]
    paths = {
        "skill_md_path": export_dir / "SKILL.md",
        "manifest_path": export_dir / "skill.manifest.json",
        "workflow_path": export_dir / "workflow.canvas.json",
        "package_path": export_dir / "skill.package.json",
        "readme_path": export_dir / "README.md",
        "run_guide_path": export_dir / "RUN_WORKFLOW.md",
        "ignore_path": export_dir / ".clawhubignore",
    }

    paths["skill_md_path"].write_text(_build_skill_md(package), encoding="utf-8")
    paths["manifest_path"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["workflow_path"].write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["package_path"].write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["readme_path"].write_text(_build_readme(package), encoding="utf-8")
    paths["run_guide_path"].write_text(_build_run_workflow_guide(package), encoding="utf-8")
    paths["ignore_path"].write_text("exports/\n*.zip\n__pycache__/\n.DS_Store\n", encoding="utf-8")
    return paths


def _build_skill_md(package: dict[str, Any]) -> str:
    manifest = package["manifest"]
    workflow = package["workflow"]
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    requirements = _derive_openclaw_requirements(workflow, manifest)
    display_name = _normalize_skill_name(manifest.get("name") or workflow.get("name") or "clawcanvas_skill")
    skill_slug = _official_skill_slug(manifest.get("name") or workflow.get("name") or display_name)
    description = manifest.get("description") or workflow.get("description") or "ClawCanvas exported skill."
    metadata = {
        "openclaw": {
            **requirements,
            "skillKey": skill_slug,
            "homepage": manifest.get("homepage") or "https://github.com/BUPT-GAMMA/MASFactory",
            "repository": manifest.get("repository") or "https://github.com/BUPT-GAMMA/MASFactory",
            "sourceApplication": "ClawCanvas",
            "runtimeEngine": "MASFactory",
        }
    }
    frontmatter = _yaml_frontmatter(
        {
            "name": skill_slug,
            "description": str(description),
            "version": str(manifest.get("version") or "0.1.0"),
            "metadata": metadata,
        }
    )

    tools = manifest.get("tools") or []
    knowledge = manifest.get("knowledge") or []
    behavior = manifest.get("behavior") or {}
    inputs = workflow.get("inputs") or {}
    attributes = workflow.get("attributes") or {}
    key_descriptions = workflow.get("key_descriptions") or {}

    return f"""{frontmatter}
# {display_name}

{description}

## When To Use

Use this skill when the user needs the workflow described by this package. The workflow was designed in ClawCanvas and modeled for MASFactory execution.

## How This Skill Runs

This skill includes the exact workflow graph and runtime metadata, but a compatible MASFactory runner must be present in the execution environment. If the environment cannot execute MASFactory graphs directly, use the attached files and `RUN_WORKFLOW.md` to reconstruct and run the workflow exactly.

## Reconstruction Contract

- Reconstruct the workflow exactly from the serialized data in this file.
- Prefer the attached files `workflow.canvas.json` and `skill.manifest.json` when the runtime can read bundled files.
- If bundled files are unavailable, use the embedded JSON blocks in this markdown as the source of truth.
- Do not compress, summarize, or reinterpret node logic when rebuilding. Preserve node ids, edge ids, key mappings, prompts, tools, loop controller mappings, and termination rules exactly.

## Runtime Requirements

{_format_requirements_markdown(requirements)}

## Installation Notes

- Install Python 3.10 or newer.
- Install MASFactory in the execution environment.
- Install any additional Python packages required by declared API tools, memories, or retrievers.
- Provide the required environment variables before running workflows that call external models or services.

## Tools

{_format_tools_markdown(tools)}

## Domain Knowledge

{_format_knowledge_markdown(knowledge)}

## Behavior Rules

{_format_behavior_markdown(behavior)}

## Workflow Summary

- Nodes: {len(nodes)}
- Edges: {len(edges)}
- Engine: MASFactory
- Source application: ClawCanvas

## Workflow Identity

- Document id: `{workflow.get("id") or ""}`
- Workflow name: `{workflow.get("name") or ""}`
- Description: {workflow.get("description") or "No description provided."}

## Workflow Inputs

{_json_block(inputs)}

## Workflow Attributes

{_json_block(attributes)}

## Workflow Key Descriptions

{_json_block(key_descriptions)}

## Workflow Topology

{_format_edge_list(edges)}

## Node Specifications

{_format_node_sections(nodes)}

## Workflow Files

- `workflow.canvas.json`: full ClawCanvas workflow graph.
- `skill.manifest.json`: structured skill metadata.
- `skill.package.json`: complete exported package including last run metadata.
- `RUN_WORKFLOW.md`: execution guide for MASFactory environments.

## Agent Instructions

When using this skill, inspect `workflow.canvas.json` first. Rebuild or execute the graph exactly as specified, including node ids, edge ids, key mappings, prompt templates, custom Python logic, tool bindings, loop controller mappings, and termination rules. Follow the behavior rules and domain knowledge above. If required credentials are missing, request the declared environment variables before execution.

## Exact Skill Manifest JSON

{_json_block(manifest)}

## Exact Workflow Canvas JSON

{_json_block(workflow)}

---

Exported from ClawCanvas at {package["exported_at"]}.
"""


def _build_readme(package: dict[str, Any]) -> str:
    manifest = package["manifest"]
    workflow = package["workflow"]
    display_name = _normalize_skill_name(manifest.get("name") or workflow.get("name") or "ClawCanvas Skill")
    skill_slug = _official_skill_slug(manifest.get("name") or workflow.get("name") or display_name)
    return f"""# {display_name}

{manifest.get("description") or workflow.get("description") or "No description provided."}

This folder is intended to be published to ClawHub/OpenClaw as a text-based skill bundle.

Skill key: `{skill_slug}`

## Required Entry Point

- `SKILL.md`: OpenClaw/ClawHub skill entry file with YAML frontmatter and instructions.

## Supporting Files

- `workflow.canvas.json`: complete ClawCanvas workflow definition.
- `skill.manifest.json`: skill metadata from the ClawCanvas manifest editor.
- `skill.package.json`: combined export payload.
- `RUN_WORKFLOW.md`: execution guide for MASFactory environments.
- `.clawhubignore`: publish/sync ignore rules.

## Notes

ClawHub requires `SKILL.md`. This export embeds the exact workflow JSON inside `SKILL.md` and also ships standalone JSON files so OpenClaw users, ClawCanvas, and future importers can reconstruct the workflow.
"""


def _build_run_workflow_guide(package: dict[str, Any]) -> str:
    manifest = package["manifest"]
    workflow = package["workflow"]
    requirements = _derive_openclaw_requirements(workflow, manifest)
    env_requirements = (requirements.get("requires") or {}).get("env") or []
    deps = _python_dependencies_for_workflow(workflow, manifest)
    deps_text = " ".join(deps) if deps else "masfactory"
    env_text = "\n".join(f"- `{item}`" for item in env_requirements) or "- No required environment variables were inferred."
    return f"""# Run This Workflow

This file explains how to execute the ClawCanvas workflow outside of the skill metadata parser.

## Requirements

- Python 3.10 or newer.
- MASFactory installed in the Python environment.
- Access to the files in this skill folder.

Environment variables:

{env_text}

Python packages inferred from the workflow:

```bash
python -m pip install {deps_text}
```

If `masfactory` is not available from your configured package index, install it from the MASFactory repository or run this workflow inside a MASFactory checkout.

## Workflow Files

- `workflow.canvas.json` is the source of truth for nodes, edges, keys, prompts, tool declarations, loop controller mappings, and custom node logic.
- `skill.manifest.json` contains skill-level tools, knowledge, behavior, tags, and metadata.
- `skill.package.json` combines the manifest, workflow, runtime metadata, warnings, and last run output.

## Execution Contract

1. Load `workflow.canvas.json`.
2. Reconstruct the MASFactory graph using the node and edge definitions exactly.
3. Use `document.inputs` as the graph entry payload.
4. Use `document.attributes` as initial MASFactory graph attributes.
5. Bind declared tools, memories, and retrievers before invoking agent or loop nodes.
6. Preserve loop `controller_inputs`, `controller_outputs`, and termination rules.
7. Preserve custom node Python logic exactly.

## Current Boundary

OpenClaw skills are instruction bundles. They can include supporting files, but OpenClaw does not automatically know how to execute a custom MASFactory graph unless a compatible runner is installed. This skill therefore includes both human/agent instructions and the exact workflow JSON needed by a runner.
"""


def _derive_openclaw_requirements(workflow: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    env: set[str] = set()
    bins: set[str] = set()
    deps: set[str] = set()
    has_agent = any(_node_or_inner_has_type(node, "agent") for node in workflow.get("nodes") or [])
    if has_agent:
        env.add("OPENAI_API_KEY")
    if has_agent or _workflow_has_loop(workflow) or _workflow_has_custom_python(workflow):
        bins.add("python")
        deps.add("masfactory")
    if _manifest_has_api_tools(manifest) or _workflow_has_api_tools(workflow):
        bins.add("python")
        deps.add("requests")
    if _workflow_has_memory_or_retriever(workflow):
        bins.add("python")
        deps.update({"numpy", "scikit-learn"})

    requires: dict[str, Any] = {}
    if env:
        requires["env"] = sorted(env)
    if bins:
        requires["bins"] = sorted(bins)
    if deps:
        requires["python"] = sorted(deps)

    out: dict[str, Any] = {}
    if requires:
        out["requires"] = requires
    if env:
        out["primaryEnv"] = sorted(env)[0]
    return out


def _node_or_inner_has_type(node: dict[str, Any], node_type: str) -> bool:
    if node.get("type") == node_type:
        return True
    subgraph = dict((node.get("config") or {}).get("subgraph") or {})
    return any(_node_or_inner_has_type(inner, node_type) for inner in (subgraph.get("nodes") or []))


def _workflow_has_loop(workflow: dict[str, Any]) -> bool:
    return any(_node_or_inner_has_type(node, "loop") for node in workflow.get("nodes") or [])


def _workflow_has_custom_python(workflow: dict[str, Any]) -> bool:
    def node_has_custom_python(node: dict[str, Any]) -> bool:
        config = dict(node.get("config") or {})
        if node.get("type") == "custom" and str(config.get("mode") or "").strip().lower() == "python":
            return True
        subgraph = dict(config.get("subgraph") or {})
        return any(node_has_custom_python(inner) for inner in (subgraph.get("nodes") or []))

    return any(node_has_custom_python(node) for node in workflow.get("nodes") or [])


def _manifest_has_api_tools(manifest: dict[str, Any]) -> bool:
    return any(str(tool.get("binding") or "").lower() == "api" for tool in (manifest.get("tools") or []))


def _workflow_has_api_tools(workflow: dict[str, Any]) -> bool:
    def node_has_api(node: dict[str, Any]) -> bool:
        config = dict(node.get("config") or {})
        if any(str(tool.get("binding") or "").lower() == "api" for tool in (config.get("tools") or [])):
            return True
        controller = dict(config.get("controller") or {})
        if any(str(tool.get("binding") or "").lower() == "api" for tool in (controller.get("tools") or [])):
            return True
        subgraph = dict(config.get("subgraph") or {})
        return any(node_has_api(inner) for inner in (subgraph.get("nodes") or []))

    return any(node_has_api(node) for node in (workflow.get("nodes") or []))


def _workflow_has_memory_or_retriever(workflow: dict[str, Any]) -> bool:
    def node_has_capabilities(node: dict[str, Any]) -> bool:
        config = dict(node.get("config") or {})
        controller = dict(config.get("controller") or {})
        if controller.get("memories") or controller.get("retrievers"):
            return True
        subgraph = dict(config.get("subgraph") or {})
        return any(node_has_capabilities(inner) for inner in (subgraph.get("nodes") or []))

    return any(node_has_capabilities(node) for node in workflow.get("nodes") or [])


def _python_dependencies_for_workflow(workflow: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    requirements = _derive_openclaw_requirements(workflow, manifest)
    return list(((requirements.get("requires") or {}).get("python") or []))


def _format_requirements_markdown(requirements: dict[str, Any]) -> str:
    requires = requirements.get("requires") or {}
    lines = []
    if requires.get("env"):
        lines.append("Environment variables:")
        lines.extend(f"- `{item}`" for item in requires["env"])
    if requires.get("bins"):
        lines.append("CLI binaries:")
        lines.extend(f"- `{item}`" for item in requires["bins"])
    if requires.get("python"):
        lines.append("Python packages:")
        lines.extend(f"- `{item}`" for item in requires["python"])
    return "\n".join(lines) if lines else "No external requirements declared."


def _format_tools_markdown(tools: list[dict[str, Any]]) -> str:
    if not tools:
        return "No skill-level tools declared."
    return "\n".join(
        f"- `{tool.get('name', 'unnamed')}` (`{tool.get('binding', 'unknown')}`): {tool.get('description', '') or 'No description.'}"
        for tool in tools
    )


def _format_knowledge_markdown(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No skill-level knowledge declared."
    return "\n\n".join(f"### {item.get('title') or 'Knowledge'}\n\n{item.get('text') or ''}" for item in items)


def _format_behavior_markdown(behavior: dict[str, Any]) -> str:
    if not behavior:
        return "No skill-level behavior declared."
    lines = []
    if behavior.get("style"):
        lines.append(f"- Style: {behavior['style']}")
    for rule in behavior.get("rules") or []:
        lines.append(f"- {rule}")
    return "\n".join(lines) if lines else "No skill-level behavior declared."


def _json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def _format_edge_list(edges: list[dict[str, Any]]) -> str:
    if not edges:
        return "No workflow edges declared."
    lines = []
    for edge in edges:
        lines.append(
            f"- `{edge.get('id', 'edge')}`: `{edge.get('source', '?')}` -> `{edge.get('target', '?')}` with mapping `{json.dumps(edge.get('mapping') or {}, ensure_ascii=False)}`"
        )
    return "\n".join(lines)


def _format_node_sections(nodes: list[dict[str, Any]], *, level: int = 3, owner_path: str = "workflow") -> str:
    if not nodes:
        return "No nodes declared."

    sections: list[str] = []
    heading_prefix = "#" * max(3, min(level, 6))

    for node in nodes:
        node_id = str(node.get("id") or "node")
        node_type = str(node.get("type") or "unknown")
        label = str(node.get("label") or node_id)
        config = dict(node.get("config") or {})
        position = dict(node.get("position") or {})
        sections.append(
            "\n".join(
                [
                    f"{heading_prefix} Node `{node_id}` ({node_type})",
                    "",
                    f"- Path: `{owner_path}/{node_id}`",
                    f"- Label: {label}",
                    f"- Position: `x={position.get('x', 0)}`, `y={position.get('y', 0)}`",
                    "",
                    "Config:",
                    "",
                    _json_block(config),
                ]
            )
        )

        if node_type == "loop":
            controller_inputs = config.get("controller_inputs") or []
            controller_outputs = config.get("controller_outputs") or []
            inner_edges = (config.get("subgraph") or {}).get("edges") or []
            inner_nodes = (config.get("subgraph") or {}).get("nodes") or []
            sections.append(
                "\n".join(
                    [
                        "",
                        f"{heading_prefix}# Loop `{node_id}` Controller Topology",
                        "",
                        "Controller Inputs:",
                        "",
                        _json_block(controller_inputs),
                        "",
                        "Controller Outputs:",
                        "",
                        _json_block(controller_outputs),
                        "",
                        "Inner Edges:",
                        "",
                        _json_block(inner_edges),
                    ]
                )
            )
            sections.append(
                _format_node_sections(
                    inner_nodes,
                    level=level + 1,
                    owner_path=f"{owner_path}/{node_id}/subgraph",
                )
            )

    return "\n\n".join(section for section in sections if section.strip())


def _slugify(value: str) -> str:
    chars = []
    for char in str(value).strip().lower():
        if char.isalnum():
            chars.append(char)
        elif char in {" ", "_", "-", "/"}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "clawcanvas-skill"


def _official_skill_slug(value: str) -> str:
    slug = _slugify(str(value).replace("_", "-"))
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        slug = "clawcanvas-skill"
    return slug


def _normalize_skill_name(value: str) -> str:
    chars = []
    for char in str(value).strip().lower():
        if char.isalnum():
            chars.append(char)
        elif char in {" ", "-", "/", "."}:
            chars.append("_")
        elif char == "_":
            chars.append("_")
    normalized = "".join(chars).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized or "clawcanvas_skill"


def _yaml_frontmatter(data: dict[str, Any]) -> str:
    return "---\n" + _yaml_lines(data) + "\n---"


def _yaml_lines(value: Any, *, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key_text}:")
                lines.append(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{pad}{key_text}: {_yaml_scalar(item)}")
        return "\n".join(line for line in lines if line != "")
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(_yaml_lines(item, indent=indent + 2))
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_yaml_scalar(value)}"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)
