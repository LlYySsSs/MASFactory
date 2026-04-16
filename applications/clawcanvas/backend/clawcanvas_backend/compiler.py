from __future__ import annotations

from dataclasses import dataclass, field
from string import Formatter
from typing import Any

from .schema import CanvasDocument, CanvasNode


@dataclass(slots=True)
class CompileWarnings:
    items: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        if message and message not in self.items:
            self.items.append(message)


def build_model(*, api_key: str, model_name: str, base_url: str | None = None):
    from masfactory import OpenAIModel

    return OpenAIModel(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
    )


def compile_document_to_graph(
    document: CanvasDocument,
    *,
    api_key: str,
    model_name: str = "gpt-4o-mini",
    base_url: str | None = None,
):
    from masfactory.components.graphs.root_graph import RootGraph

    model = build_model(api_key=api_key, model_name=model_name, base_url=base_url)
    warnings = CompileWarnings()
    graph = RootGraph(name=_safe_graph_name(document.name), attributes=dict(document.attributes))

    runtime_nodes: dict[str, Any] = {}
    for node in document.nodes:
        if node.type == "agent":
            runtime_nodes[node.id] = _create_agent_node(graph, node, warnings, model)
        elif node.type == "custom":
            runtime_nodes[node.id] = _create_custom_node(graph, node, warnings)
        elif node.type == "loop":
            runtime_nodes[node.id] = _create_loop_node(graph, node, warnings, model)

    for edge in document.edges:
        source_node = _find_node(document, edge.source)
        target_node = _find_node(document, edge.target)
        if source_node.type == "start" and target_node.type in {"agent", "custom", "loop"}:
            graph.edge_from_entry(runtime_nodes[target_node.id], keys=dict(edge.mapping))
            continue
        if source_node.type in {"agent", "custom", "loop"} and target_node.type == "end":
            graph.edge_to_exit(runtime_nodes[source_node.id], keys=dict(edge.mapping))
            continue
        if source_node.type in {"agent", "custom", "loop"} and target_node.type in {"agent", "custom", "loop"}:
            graph.create_edge(runtime_nodes[source_node.id], runtime_nodes[target_node.id], keys=dict(edge.mapping))
            continue
        raise ValueError(f"unsupported edge in MVP: {source_node.type} -> {target_node.type}")

    graph.build()
    return graph, warnings


def _create_agent_node(graph, node: CanvasNode, warnings: CompileWarnings, model):
    from masfactory.components.agents.agent import Agent

    config = dict(node.config)
    tools = list(config.get("tools") or [])
    if tools:
        warnings.add(
            f"node '{node.id}' defines {len(tools)} tool entries, but tool binding is metadata-only in the MVP"
        )

    instructions = _compose_agent_instructions(config)
    prompt_template = str(config.get("prompt_template") or "{message}")
    pull_keys = _normalize_keys(config.get("pull_keys")) or {}
    push_keys = _normalize_keys(config.get("push_keys")) or {}
    attributes = dict(config.get("attributes") or {})
    model_settings = dict(config.get("model_settings") or {})

    return graph.create_node(
        Agent,
        name=node.id,
        instructions=instructions,
        model=model,
        prompt_template=prompt_template,
        pull_keys=pull_keys,
        push_keys=push_keys,
        attributes=attributes,
        role_name=str(config.get("role_name") or node.label or node.id),
        model_settings=model_settings,
    )


def _create_custom_node(graph, node: CanvasNode, warnings: CompileWarnings):
    from masfactory.components.custom_node import CustomNode

    config = dict(node.config)
    mode = str(config.get("mode") or "passthrough").strip()
    pull_keys = _normalize_keys(config.get("pull_keys")) or {}
    push_keys = _normalize_keys(config.get("push_keys")) or {}
    attributes = dict(config.get("attributes") or {})
    forward = _build_custom_forward(node.id, mode, config, warnings)

    return graph.create_node(
        CustomNode,
        name=node.id,
        forward=forward,
        pull_keys=pull_keys,
        push_keys=push_keys,
        attributes=attributes,
    )


def _create_loop_node(graph, node: CanvasNode, warnings: CompileWarnings, model):
    from masfactory.components.graphs.loop import Loop

    config = dict(node.config)
    body = dict(config.get("body") or {})
    max_iterations = int(config.get("max_iterations") or 3)
    loop_pull_keys = _normalize_keys(config.get("pull_keys")) or _normalize_keys(body.get("input_mapping")) or {}
    loop_push_keys = _normalize_keys(config.get("push_keys")) or _normalize_keys(body.get("output_mapping")) or {}
    loop_attributes = dict(config.get("attributes") or {})

    loop = graph.create_node(
        Loop,
        name=node.id,
        max_iterations=max_iterations,
        terminate_condition_function=_build_loop_terminate_function(config),
        pull_keys=loop_pull_keys,
        push_keys=loop_push_keys,
        attributes=loop_attributes,
    )

    body_type = str(body.get("type") or "agent").strip()
    input_mapping = _normalize_keys(body.get("input_mapping")) or _normalize_keys(body.get("pull_keys")) or {"message": "Loop input"}
    output_mapping = _normalize_keys(body.get("output_mapping")) or _normalize_keys(body.get("push_keys")) or {"message": "Loop output"}

    if body_type == "agent":
        body_node = _create_loop_body_agent(loop, node.id, body, warnings, model, input_mapping, output_mapping)
    elif body_type == "custom":
        body_node = _create_loop_body_custom(loop, node.id, body, warnings, input_mapping, output_mapping)
    else:
        raise ValueError(f"unsupported loop body type: {body_type}")

    loop.edge_from_controller(body_node, keys=input_mapping)
    loop.edge_to_controller(body_node, keys=output_mapping)
    return loop


def _create_loop_body_agent(loop, node_id: str, body: dict[str, Any], warnings: CompileWarnings, model, input_mapping: dict[str, str], output_mapping: dict[str, str]):
    from masfactory.components.agents.agent import Agent

    tools = list(body.get("tools") or [])
    if tools:
        warnings.add(
            f"loop '{node_id}' body defines {len(tools)} tool entries, but tool binding is metadata-only in the MVP"
        )

    instructions = _compose_agent_instructions(body)
    prompt_template = str(body.get("prompt_template") or "{message}")
    pull_keys = _normalize_keys(body.get("pull_keys")) or input_mapping
    push_keys = _normalize_keys(body.get("push_keys")) or output_mapping
    attributes = dict(body.get("attributes") or {})
    model_settings = dict(body.get("model_settings") or {})

    return loop.create_node(
        Agent,
        name=f"{node_id}_body",
        instructions=instructions,
        model=model,
        prompt_template=prompt_template,
        pull_keys=pull_keys,
        push_keys=push_keys,
        attributes=attributes,
        role_name=str(body.get("role_name") or f"{node_id} body"),
        model_settings=model_settings,
    )


def _create_loop_body_custom(loop, node_id: str, body: dict[str, Any], warnings: CompileWarnings, input_mapping: dict[str, str], output_mapping: dict[str, str]):
    from masfactory.components.custom_node import CustomNode

    mode = str(body.get("mode") or "passthrough").strip()
    attributes = dict(body.get("attributes") or {})
    forward = _build_custom_forward(f"{node_id}_body", mode, body, warnings)

    return loop.create_node(
        CustomNode,
        name=f"{node_id}_body",
        forward=forward,
        pull_keys=_normalize_keys(body.get("pull_keys")) or input_mapping,
        push_keys=_normalize_keys(body.get("push_keys")) or output_mapping,
        attributes=attributes,
    )


def _compose_agent_instructions(config: dict[str, Any]) -> str:
    base = str(config.get("instructions") or "").strip()
    behavior_rules = [str(item).strip() for item in (config.get("behavior_rules") or []) if str(item).strip()]
    knowledge_items = []
    for item in (config.get("knowledge") or []):
        if isinstance(item, dict):
            title = str(item.get("title") or "Knowledge").strip()
            text = str(item.get("text") or "").strip()
            if text:
                knowledge_items.append(f"{title}: {text}")
        elif isinstance(item, str) and item.strip():
            knowledge_items.append(item.strip())

    sections = [base] if base else []
    if knowledge_items:
        sections.append("Domain knowledge:\n- " + "\n- ".join(knowledge_items))
    if behavior_rules:
        sections.append("Behavior rules:\n- " + "\n- ".join(behavior_rules))
    return "\n\n".join(section for section in sections if section).strip()


def _build_custom_forward(node_id: str, mode: str, config: dict[str, Any], warnings: CompileWarnings):
    if mode not in {"passthrough", "template", "set", "pick"}:
        raise ValueError(f"custom node '{node_id}' has unsupported mode '{mode}'")

    templates = dict(config.get("templates") or {})
    static_outputs = config.get("static_outputs") or config.get("outputs") or {}
    picks = dict(config.get("pick_keys") or {})

    if mode == "template" and not templates:
        warnings.add(f"custom node '{node_id}' uses template mode with no templates configured")
    if mode == "set" and not isinstance(static_outputs, dict):
        raise ValueError(f"custom node '{node_id}' static_outputs must be a dict")

    def forward(input_dict: dict[str, object], attributes: dict[str, object] | None = None) -> dict[str, object]:
        attrs = attributes or {}
        context = {**attrs, **input_dict}

        if mode == "passthrough":
            return dict(input_dict)
        if mode == "template":
            return {key: _render_template(str(value), context) for key, value in templates.items()}
        if mode == "set":
            return _resolve_payload(static_outputs, context)
        if mode == "pick":
            out: dict[str, object] = {}
            for out_key, in_key in picks.items():
                out[str(out_key)] = context.get(str(in_key))
            return out
        raise ValueError(f"unsupported custom node mode: {mode}")

    return forward


def _build_loop_terminate_function(config: dict[str, Any]):
    terminate = dict(config.get("terminate_when") or {})
    mode = str(terminate.get("mode") or "never").strip()
    key = str(terminate.get("key") or "").strip()
    value = terminate.get("value")

    def _terminate(input_dict: dict[str, object], attributes: dict[str, object]) -> bool:
        source = {**attributes, **input_dict}
        if mode == "never":
            return False
        if mode == "key_truthy":
            return bool(source.get(key)) if key else False
        if mode == "key_equals":
            return source.get(key) == value if key else False
        raise ValueError(f"unsupported loop terminate mode: {mode}")

    return _terminate


def _normalize_keys(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("pull_keys/push_keys must be dict values")
    return {str(key): str(value) for key, value in raw.items()}


def _render_template(template: str, context: dict[str, object]) -> str:
    formatter = Formatter()
    parts: list[str] = []
    for literal_text, field_name, format_spec, conversion in formatter.parse(template):
        parts.append(literal_text)
        if field_name is None:
            continue
        value = context.get(field_name, "{" + field_name + "}")
        if conversion == "r":
            value = repr(value)
        elif conversion == "s":
            value = str(value)
        if format_spec:
            try:
                value = format(value, format_spec)
            except Exception:
                value = str(value)
        parts.append(str(value))
    return "".join(parts)


def _resolve_payload(value: Any, context: dict[str, object]) -> Any:
    if isinstance(value, str):
        return _render_template(value, context)
    if isinstance(value, list):
        return [_resolve_payload(item, context) for item in value]
    if isinstance(value, dict):
        return {str(key): _resolve_payload(item, context) for key, item in value.items()}
    return value


def _safe_graph_name(name: str) -> str:
    safe = []
    for char in str(name).strip().lower():
        if char.isalnum() or char == "_":
            safe.append(char)
        elif char in {" ", "-", "/"}:
            safe.append("_")
    collapsed = "".join(safe).strip("_")
    return collapsed or "clawcanvas_graph"


def _find_node(document: CanvasDocument, node_id: str) -> CanvasNode:
    for node in document.nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"unknown node id: {node_id}")
