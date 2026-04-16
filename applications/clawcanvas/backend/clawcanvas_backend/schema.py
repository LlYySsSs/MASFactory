from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SUPPORTED_NODE_TYPES = {"start", "agent", "custom", "loop", "end"}


@dataclass(slots=True)
class Position:
    x: float
    y: float


@dataclass(slots=True)
class CanvasNode:
    id: str
    type: str
    label: str
    position: Position
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanvasEdge:
    id: str
    source: str
    target: str
    mapping: dict[str, str] = field(default_factory=lambda: {"message": "message"})


@dataclass(slots=True)
class SkillManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    behavior: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanvasDocument:
    id: str
    name: str
    description: str
    nodes: list[CanvasNode]
    edges: list[CanvasEdge]
    inputs: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    manifest: SkillManifest = field(default_factory=lambda: SkillManifest(name="unnamed_skill"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_str(raw: Any, field_name: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return raw.strip()


def _coerce_mapping(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("mapping-like value must be a dict")
    out: dict[str, str] = {}
    for key, value in raw.items():
        out[str(key)] = str(value)
    return out


def parse_document(payload: dict[str, Any]) -> CanvasDocument:
    if not isinstance(payload, dict):
        raise ValueError("document payload must be a dict")

    nodes_raw = payload.get("nodes")
    edges_raw = payload.get("edges")
    if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
        raise ValueError("document payload must contain list fields: nodes and edges")

    nodes: list[CanvasNode] = []
    for item in nodes_raw:
        if not isinstance(item, dict):
            raise ValueError("each node must be a dict")
        pos = item.get("position") or {}
        if not isinstance(pos, dict):
            raise ValueError("node.position must be a dict")
        nodes.append(
            CanvasNode(
                id=_require_str(item.get("id"), "node.id"),
                type=_require_str(item.get("type"), "node.type"),
                label=str(item.get("label") or item.get("id")).strip(),
                position=Position(
                    x=float(pos.get("x", 0)),
                    y=float(pos.get("y", 0)),
                ),
                config=dict(item.get("config") or {}),
            )
        )

    edges: list[CanvasEdge] = []
    for item in edges_raw:
        if not isinstance(item, dict):
            raise ValueError("each edge must be a dict")
        edges.append(
            CanvasEdge(
                id=_require_str(item.get("id"), "edge.id"),
                source=_require_str(item.get("source"), "edge.source"),
                target=_require_str(item.get("target"), "edge.target"),
                mapping=_coerce_mapping(item.get("mapping")) or {"message": "message"},
            )
        )

    manifest_raw = payload.get("manifest") or {}
    if not isinstance(manifest_raw, dict):
        raise ValueError("manifest must be a dict")

    manifest = SkillManifest(
        name=_require_str(manifest_raw.get("name") or payload.get("name") or "clawcanvas_skill", "manifest.name"),
        version=str(manifest_raw.get("version") or "0.1.0"),
        description=str(manifest_raw.get("description") or payload.get("description") or ""),
        tags=[str(item) for item in (manifest_raw.get("tags") or [])],
        tools=[dict(item) for item in (manifest_raw.get("tools") or [])],
        knowledge=[dict(item) for item in (manifest_raw.get("knowledge") or [])],
        behavior=dict(manifest_raw.get("behavior") or {}),
    )

    document = CanvasDocument(
        id=_require_str(payload.get("id") or "clawcanvas_doc", "document.id"),
        name=_require_str(payload.get("name") or "ClawCanvas Workflow", "document.name"),
        description=str(payload.get("description") or ""),
        nodes=nodes,
        edges=edges,
        inputs=dict(payload.get("inputs") or {}),
        attributes=dict(payload.get("attributes") or {}),
        manifest=manifest,
    )
    validate_document(document)
    return document


def validate_document(document: CanvasDocument) -> None:
    node_ids = [node.id for node in document.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("node ids must be unique")

    edge_ids = [edge.id for edge in document.edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("edge ids must be unique")

    nodes_by_id = {node.id: node for node in document.nodes}
    start_nodes = [node for node in document.nodes if node.type == "start"]
    end_nodes = [node for node in document.nodes if node.type == "end"]
    if len(start_nodes) != 1:
        raise ValueError("workflow must contain exactly one start node")
    if len(end_nodes) != 1:
        raise ValueError("workflow must contain exactly one end node")

    for node in document.nodes:
        if node.type not in SUPPORTED_NODE_TYPES:
            raise ValueError(f"unsupported node type: {node.type}")
        if node.type == "agent" and not str(node.config.get("instructions") or "").strip():
            raise ValueError(f"agent node '{node.id}' must define instructions")
        if node.type == "custom":
            mode = str(node.config.get("mode") or "passthrough").strip()
            if mode not in {"passthrough", "template", "set", "pick"}:
                raise ValueError(f"custom node '{node.id}' has unsupported mode '{mode}'")
        if node.type == "loop":
            body = node.config.get("body") or {}
            if not isinstance(body, dict):
                raise ValueError(f"loop node '{node.id}' body must be a dict")
            body_type = str(body.get("type") or "agent").strip()
            if body_type not in {"agent", "custom"}:
                raise ValueError(
                    f"loop node '{node.id}' body.type must be 'agent' or 'custom'"
                )
            if body_type == "agent" and not str(body.get("instructions") or "").strip():
                raise ValueError(
                    f"loop node '{node.id}' with agent body must define body.instructions"
                )

    incoming: dict[str, list[str]] = {node.id: [] for node in document.nodes}
    outgoing: dict[str, list[str]] = {node.id: [] for node in document.nodes}
    for edge in document.edges:
        if edge.source not in nodes_by_id or edge.target not in nodes_by_id:
            raise ValueError(f"edge '{edge.id}' references an unknown node")
        if edge.source == edge.target:
            raise ValueError(f"edge '{edge.id}' must not point to the same node")
        source_type = nodes_by_id[edge.source].type
        target_type = nodes_by_id[edge.target].type
        if target_type == "start":
            raise ValueError(f"edge '{edge.id}' must not target the start node")
        if source_type == "end":
            raise ValueError(f"edge '{edge.id}' must not leave the end node")
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)

    start = start_nodes[0]
    end = end_nodes[0]
    if incoming[start.id]:
        raise ValueError("start node must not have incoming edges")
    if outgoing[end.id]:
        raise ValueError("end node must not have outgoing edges")

    _assert_reachable(start.id, end.id, outgoing)
    _assert_acyclic(nodes_by_id, outgoing)


def _assert_reachable(start_id: str, end_id: str, outgoing: dict[str, list[str]]) -> None:
    seen = set()
    stack = [start_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(outgoing.get(current, []))
    if end_id not in seen:
        raise ValueError("workflow end node is not reachable from start")


def _assert_acyclic(nodes_by_id: dict[str, CanvasNode], outgoing: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError("workflow must be acyclic in the current MVP")
        visiting.add(node_id)
        for nxt in outgoing.get(node_id, []):
            visit(nxt)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes_by_id:
        visit(node_id)


def build_demo_document() -> CanvasDocument:
    payload = {
        "id": "demo_clawcanvas",
        "name": "ClawCanvas Demo Skill",
        "description": "A skill workflow combining agent and custom nodes compiled by MASFactory.",
        "inputs": {
            "query": "Give me a launch plan for a MASFactory-based skill studio."
        },
        "manifest": {
            "name": "clawcanvas_demo_skill",
            "version": "0.1.0",
            "description": "Demo skill package exported from ClawCanvas.",
            "tags": ["demo", "workflow", "skill"],
            "tools": [
                {"name": "web_search", "binding": "future", "description": "Reserved tool binding"}
            ],
            "knowledge": [
                {"title": "Skill Definition", "text": "Skill = tools + domain knowledge + behavior rules."}
            ],
            "behavior": {
                "style": "structured",
                "rules": [
                    "Prefer concrete deliverables.",
                    "Explain tradeoffs briefly."
                ]
            },
        },
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "label": "Start",
                "position": {"x": 80, "y": 220},
                "config": {},
            },
            {
                "id": "researcher",
                "type": "agent",
                "label": "Researcher",
                "position": {"x": 340, "y": 140},
                "config": {
                    "instructions": "You analyze the user's request and extract the essential workflow goals.",
                    "prompt_template": "User request: {query}",
                    "pull_keys": {"query": "Original user request"},
                    "push_keys": {"analysis": "Structured analysis of the request"},
                    "behavior_rules": [
                        "Keep the analysis concise.",
                        "Focus on workflow scope and assumptions.",
                    ],
                },
            },
            {
                "id": "formatter",
                "type": "custom",
                "label": "Formatter",
                "position": {"x": 680, "y": 80},
                "config": {
                    "mode": "template",
                    "templates": {
                        "analysis_card": "Summary: {analysis}"
                    },
                    "pull_keys": {"analysis": "Structured workflow analysis"},
                    "push_keys": {"analysis_card": "Formatted analysis card"},
                },
            },
            {
                "id": "designer",
                "type": "agent",
                "label": "Designer",
                "position": {"x": 980, "y": 240},
                "config": {
                    "instructions": "You turn the analysis into a skill design brief with architecture and next steps.",
                    "prompt_template": "Request: {query}\nAnalysis: {analysis}\nCard: {analysis_card}",
                    "pull_keys": {
                        "query": "Original user request",
                        "analysis": "Workflow analysis",
                        "analysis_card": "Formatted analysis card",
                    },
                    "push_keys": {"answer": "Skill design brief"},
                    "knowledge": [
                        {
                            "title": "Product Goal",
                            "text": "ClawCanvas packages MASFactory workflows into reusable publishable skills."
                        }
                    ],
                },
            },
            {
                "id": "end",
                "type": "end",
                "label": "End",
                "position": {"x": 1280, "y": 220},
                "config": {},
            },
        ],
        "edges": [
            {"id": "e1", "source": "start", "target": "researcher", "mapping": {"query": "User request"}},
            {
                "id": "e2",
                "source": "researcher",
                "target": "formatter",
                "mapping": {"analysis": "Analysis result"},
            },
            {
                "id": "e3",
                "source": "researcher",
                "target": "designer",
                "mapping": {"query": "Original request", "analysis": "Analysis result"},
            },
            {
                "id": "e4",
                "source": "formatter",
                "target": "designer",
                "mapping": {"analysis_card": "Formatted analysis card"},
            },
            {"id": "e5", "source": "designer", "target": "end", "mapping": {"answer": "Final answer"}},
        ],
    }
    return parse_document(payload)
