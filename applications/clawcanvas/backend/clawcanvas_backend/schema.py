from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SUPPORTED_NODE_TYPES = {"start", "agent", "custom", "loop", "end"}
INNER_LOOP_NODE_TYPES = {"agent", "custom", "loop"}


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
    author: str = ""
    license: str = "MIT"
    dependencies: list[str] = field(default_factory=list)
    homepage: str = ""
    repository: str = ""


@dataclass(slots=True)
class CanvasDocument:
    id: str
    name: str
    description: str
    nodes: list[CanvasNode]
    edges: list[CanvasEdge]
    inputs: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    key_descriptions: dict[str, str] = field(default_factory=dict)
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


def _parse_node(item: dict[str, Any], *, prefix: str = "node") -> CanvasNode:
    pos = item.get("position") or {}
    if not isinstance(pos, dict):
        raise ValueError(f"{prefix}.position must be a dict")
    return CanvasNode(
        id=_require_str(item.get("id"), f"{prefix}.id"),
        type=_require_str(item.get("type"), f"{prefix}.type"),
        label=str(item.get("label") or item.get("id")).strip(),
        position=Position(
            x=float(pos.get("x", 0)),
            y=float(pos.get("y", 0)),
        ),
        config=_normalize_loop_config_dict(dict(item.get("config") or {})),
    )


def _parse_edge(item: dict[str, Any], *, prefix: str = "edge") -> CanvasEdge:
    return CanvasEdge(
        id=_require_str(item.get("id"), f"{prefix}.id"),
        source=_require_str(item.get("source"), f"{prefix}.source"),
        target=_require_str(item.get("target"), f"{prefix}.target"),
        mapping=_coerce_mapping(item.get("mapping")) or {"message": "message"},
    )


def _normalize_loop_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    if "subgraph" in config:
        subgraph = dict(config.get("subgraph") or {})
        return {
            **config,
            "max_iterations": int(config.get("max_iterations") or 3),
            "terminate_when": dict(config.get("terminate_when") or {"mode": "never", "key": "", "value": True}),
            "controller": {
                "termination_mode": str(dict(config.get("controller") or {}).get("termination_mode") or "key_rule"),
                "terminate_condition_prompt": str(
                    dict(config.get("controller") or {}).get("terminate_condition_prompt") or ""
                ),
                "terminate_expression": str(dict(config.get("controller") or {}).get("terminate_expression") or ""),
                "model_settings": dict(dict(config.get("controller") or {}).get("model_settings") or {}),
                "tools": [dict(item) for item in (dict(config.get("controller") or {}).get("tools") or [])],
                "memories": [dict(item) for item in (dict(config.get("controller") or {}).get("memories") or [])],
                "retrievers": [dict(item) for item in (dict(config.get("controller") or {}).get("retrievers") or [])],
            },
            "subgraph": {
                "nodes": [dict(item) for item in (subgraph.get("nodes") or [])],
                "edges": [dict(item) for item in (subgraph.get("edges") or [])],
            },
            "controller_inputs": [dict(item) for item in (config.get("controller_inputs") or [])],
            "controller_outputs": [dict(item) for item in (config.get("controller_outputs") or [])],
        }

    body = dict(config.get("body") or {})
    if body:
        body_type = str(body.get("type") or "agent").strip()
        body_node_id = "loop_step_1"
        return {
            "max_iterations": int(config.get("max_iterations") or 3),
            "terminate_when": dict(config.get("terminate_when") or {"mode": "never", "key": "", "value": True}),
            "controller": {
                "termination_mode": "key_rule",
                "terminate_condition_prompt": "",
                "terminate_expression": "",
                "model_settings": {},
                "tools": [],
                "memories": [],
                "retrievers": [],
            },
            "subgraph": {
                "nodes": [
                    {
                        "id": body_node_id,
                        "type": body_type,
                        "label": "Loop Step",
                        "position": {"x": 260, "y": 180},
                        "config": {
                            **body,
                            "pull_keys": dict(body.get("pull_keys") or body.get("input_mapping") or {}),
                            "push_keys": dict(body.get("push_keys") or body.get("output_mapping") or {}),
                        },
                    }
                ],
                "edges": [],
            },
            "controller_inputs": [
                {
                    "id": "controller_in_1",
                    "target": body_node_id,
                    "mapping": dict(body.get("input_mapping") or body.get("pull_keys") or {"message": "Loop input"}),
                }
            ],
            "controller_outputs": [
                {
                    "id": "controller_out_1",
                    "source": body_node_id,
                    "mapping": dict(body.get("output_mapping") or body.get("push_keys") or {"message": "Loop output"}),
                }
            ],
        }
    return config


def parse_document(payload: dict[str, Any]) -> CanvasDocument:
    if not isinstance(payload, dict):
        raise ValueError("document payload must be a dict")

    nodes_raw = payload.get("nodes")
    edges_raw = payload.get("edges")
    if not isinstance(nodes_raw, list) or not isinstance(edges_raw, list):
        raise ValueError("document payload must contain list fields: nodes and edges")

    nodes = [_parse_node(item) for item in nodes_raw if isinstance(item, dict)]
    if len(nodes) != len(nodes_raw):
        raise ValueError("each node must be a dict")

    edges = [_parse_edge(item) for item in edges_raw if isinstance(item, dict)]
    if len(edges) != len(edges_raw):
        raise ValueError("each edge must be a dict")

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
        author=str(manifest_raw.get("author") or ""),
        license=str(manifest_raw.get("license") or "MIT"),
        dependencies=[str(item) for item in (manifest_raw.get("dependencies") or [])],
        homepage=str(manifest_raw.get("homepage") or ""),
        repository=str(manifest_raw.get("repository") or ""),
    )

    document = CanvasDocument(
        id=_require_str(payload.get("id") or "clawcanvas_doc", "document.id"),
        name=_require_str(payload.get("name") or "ClawCanvas Workflow", "document.name"),
        description=str(payload.get("description") or ""),
        nodes=nodes,
        edges=edges,
        inputs=dict(payload.get("inputs") or {}),
        attributes=dict(payload.get("attributes") or {}),
        key_descriptions=_coerce_mapping(payload.get("key_descriptions")),
        manifest=manifest,
    )
    validate_document(document)
    return document


def validate_document(document: CanvasDocument) -> None:
    _validate_graph(
        document.nodes,
        document.edges,
        require_start_end=True,
        loop_owner="workflow",
    )


def _validate_graph(nodes: list[CanvasNode], edges: list[CanvasEdge], *, require_start_end: bool, loop_owner: str) -> None:
    node_ids = [node.id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError(f"{loop_owner}: node ids must be unique")

    edge_ids = [edge.id for edge in edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError(f"{loop_owner}: edge ids must be unique")

    nodes_by_id = {node.id: node for node in nodes}

    if require_start_end:
        start_nodes = [node for node in nodes if node.type == "start"]
        end_nodes = [node for node in nodes if node.type == "end"]
        if len(start_nodes) != 1:
            raise ValueError("workflow must contain exactly one start node")
        if len(end_nodes) != 1:
            raise ValueError("workflow must contain exactly one end node")
    else:
        start_nodes = []
        end_nodes = []

    for node in nodes:
        if require_start_end:
            if node.type not in SUPPORTED_NODE_TYPES:
                raise ValueError(f"unsupported node type: {node.type}")
        else:
            if node.type not in INNER_LOOP_NODE_TYPES:
                raise ValueError(f"{loop_owner}: loop subgraph only supports agent/custom/loop nodes")

        if node.type == "agent" and not str(node.config.get("instructions") or "").strip():
            raise ValueError(f"agent node '{node.id}' must define instructions")

        if node.type == "custom":
            mode = str(node.config.get("mode") or "passthrough").strip()
            if mode not in {"passthrough", "template", "set", "pick", "compose", "python"}:
                raise ValueError(f"custom node '{node.id}' has unsupported mode '{mode}'")

        if node.type == "loop":
            _validate_loop_config(node.id, node.config or {})

    incoming: dict[str, list[str]] = {node.id: [] for node in nodes}
    outgoing: dict[str, list[str]] = {node.id: [] for node in nodes}
    for edge in edges:
        if edge.source not in nodes_by_id or edge.target not in nodes_by_id:
            raise ValueError(f"edge '{edge.id}' references an unknown node")
        if edge.source == edge.target:
            raise ValueError(f"edge '{edge.id}' must not point to the same node")
        if require_start_end:
            source_type = nodes_by_id[edge.source].type
            target_type = nodes_by_id[edge.target].type
            if target_type == "start":
                raise ValueError(f"edge '{edge.id}' must not target the start node")
            if source_type == "end":
                raise ValueError(f"edge '{edge.id}' must not leave the end node")
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)

    if require_start_end:
        start = start_nodes[0]
        end = end_nodes[0]
        if incoming[start.id]:
            raise ValueError("start node must not have incoming edges")
        if outgoing[end.id]:
            raise ValueError("end node must not have outgoing edges")
        _assert_reachable(start.id, end.id, outgoing)

    _assert_acyclic(nodes_by_id, outgoing, loop_owner=loop_owner)


def _validate_loop_config(node_id: str, config: dict[str, Any]) -> None:
    config = _normalize_loop_config_dict(dict(config or {}))
    subgraph = dict(config.get("subgraph") or {})
    inner_nodes_raw = subgraph.get("nodes")
    inner_edges_raw = subgraph.get("edges")
    if not isinstance(inner_nodes_raw, list) or not isinstance(inner_edges_raw, list):
        raise ValueError(f"loop node '{node_id}' must define subgraph.nodes and subgraph.edges")

    inner_nodes = [_parse_node(item, prefix=f"loop.{node_id}.node") for item in inner_nodes_raw if isinstance(item, dict)]
    inner_edges = [_parse_edge(item, prefix=f"loop.{node_id}.edge") for item in inner_edges_raw if isinstance(item, dict)]
    if len(inner_nodes) != len(inner_nodes_raw) or len(inner_edges) != len(inner_edges_raw):
        raise ValueError(f"loop node '{node_id}' subgraph entries must be dicts")
    if not inner_nodes:
        raise ValueError(f"loop node '{node_id}' subgraph must contain at least one node")

    _validate_graph(inner_nodes, inner_edges, require_start_end=False, loop_owner=f"loop '{node_id}'")

    controller_inputs = [dict(item) for item in (config.get("controller_inputs") or [])]
    controller_outputs = [dict(item) for item in (config.get("controller_outputs") or [])]
    if not controller_inputs:
        raise ValueError(f"loop node '{node_id}' must define at least one controller input")
    if not controller_outputs:
        raise ValueError(f"loop node '{node_id}' must define at least one controller output")

    node_ids = {node.id for node in inner_nodes}
    controller_ids: set[str] = set()
    for item in controller_inputs:
        edge_id = _require_str(item.get("id"), f"loop.{node_id}.controller_input.id")
        if edge_id in controller_ids:
            raise ValueError(f"loop node '{node_id}' controller mapping ids must be unique")
        controller_ids.add(edge_id)
        target = _require_str(item.get("target"), f"loop.{node_id}.controller_input.target")
        if target not in node_ids:
            raise ValueError(f"loop node '{node_id}' controller input '{edge_id}' targets unknown node '{target}'")
        _coerce_mapping(item.get("mapping"))

    for item in controller_outputs:
        edge_id = _require_str(item.get("id"), f"loop.{node_id}.controller_output.id")
        if edge_id in controller_ids:
            raise ValueError(f"loop node '{node_id}' controller mapping ids must be unique")
        controller_ids.add(edge_id)
        source = _require_str(item.get("source"), f"loop.{node_id}.controller_output.source")
        if source not in node_ids:
            raise ValueError(f"loop node '{node_id}' controller output '{edge_id}' references unknown node '{source}'")
        _coerce_mapping(item.get("mapping"))


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


def _assert_acyclic(nodes_by_id: dict[str, CanvasNode], outgoing: dict[str, list[str]], *, loop_owner: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError(f"{loop_owner} must remain acyclic; loops should cycle only through the MASFactory controller")
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
        "description": "A skill workflow combining agent and loop nodes compiled by MASFactory.",
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
        "key_descriptions": {
            "query": "Original user request",
            "analysis": "Structured analysis of the request",
            "draft": "Draft design brief",
            "answer": "Final design brief",
            "done": "Loop stop flag",
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
                "position": {"x": 320, "y": 140},
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
                "id": "review_loop",
                "type": "loop",
                "label": "Review Loop",
                "position": {"x": 640, "y": 220},
                "config": {
                    "max_iterations": 3,
                    "terminate_when": {"mode": "key_truthy", "key": "done", "value": True},
                    "controller": {
                        "termination_mode": "key_rule",
                        "terminate_condition_prompt": "",
                        "terminate_expression": "",
                        "model_settings": {},
                        "tools": [],
                        "memories": [],
                        "retrievers": [],
                    },
                    "subgraph": {
                        "nodes": [
                            {
                                "id": "draft_writer",
                                "type": "agent",
                                "label": "Draft Writer",
                                "position": {"x": 240, "y": 120},
                                "config": {
                                    "instructions": "Turn the analysis into a draft launch brief.",
                                    "prompt_template": "Analysis: {analysis}",
                                    "pull_keys": {"analysis": "Structured analysis"},
                                    "push_keys": {"draft": "Draft launch brief"},
                                    "behavior_rules": ["Be concise."],
                                },
                            },
                            {
                                "id": "draft_finisher",
                                "type": "custom",
                                "label": "Draft Finisher",
                                "position": {"x": 540, "y": 220},
                                "config": {
                                    "mode": "template",
                                    "templates": {
                                        "answer": "Final brief: {draft}",
                                        "done": "true",
                                    },
                                    "pull_keys": {"draft": "Draft brief"},
                                    "push_keys": {"answer": "Final brief", "done": "Stop flag"},
                                },
                            },
                        ],
                        "edges": [
                            {
                                "id": "inner_edge_1",
                                "source": "draft_writer",
                                "target": "draft_finisher",
                                "mapping": {"draft": "Draft brief"},
                            }
                        ],
                    },
                    "controller_inputs": [
                        {
                            "id": "controller_in_1",
                            "target": "draft_writer",
                            "mapping": {"analysis": "Structured analysis"},
                        }
                    ],
                    "controller_outputs": [
                        {
                            "id": "controller_out_1",
                            "source": "draft_finisher",
                            "mapping": {"answer": "Final brief", "done": "Stop flag"},
                        }
                    ],
                },
            },
            {
                "id": "end",
                "type": "end",
                "label": "End",
                "position": {"x": 980, "y": 220},
                "config": {},
            },
        ],
        "edges": [
            {"id": "edge_1", "source": "start", "target": "researcher", "mapping": {"query": "User request"}},
            {"id": "edge_2", "source": "researcher", "target": "review_loop", "mapping": {"analysis": "Analysis"}},
            {"id": "edge_3", "source": "review_loop", "target": "end", "mapping": {"answer": "Final answer"}},
        ],
    }
    return parse_document(payload)
