from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable


def builtin_echo(text: str) -> dict[str, str]:
    """Return the input text unchanged."""

    return {"text": str(text)}


def builtin_json_inspect(payload: object) -> dict[str, str]:
    """Render any payload as pretty JSON for inspection."""

    try:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    except Exception:
        rendered = str(payload)
    return {"json": rendered}


def builtin_list_keys(payload: object) -> dict[str, list[str]]:
    """List top-level keys from a dict payload."""

    if isinstance(payload, dict):
        keys = [str(key) for key in payload.keys()]
    else:
        keys = []
    return {"keys": keys}


def builtin_concat_text(left: str, right: str, separator: str = "\n") -> dict[str, str]:
    """Concatenate two text fragments with a configurable separator."""

    return {"text": f"{left}{separator}{right}"}


BUILTIN_TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "echo": builtin_echo,
    "json_inspect": builtin_json_inspect,
    "list_keys": builtin_list_keys,
    "concat_text": builtin_concat_text,
}

SUPPORTED_BUILTIN_MEMORIES = {"history_memory", "vector_memory"}
SUPPORTED_BUILTIN_RETRIEVERS = {"keyword_retriever", "vector_retriever", "filesystem_retriever"}


class RuntimeWarnings:
    def __init__(self, add_warning: Callable[[str], None]):
        self._add_warning = add_warning

    def add(self, message: str) -> None:
        if message:
            self._add_warning(message)


def resolve_agent_tools(
    declarations: list[dict[str, Any]],
    *,
    owner: str,
    warnings: RuntimeWarnings,
) -> list[Callable[..., Any]]:
    tools: list[Callable[..., Any]] = []
    seen: set[str] = set()
    for declaration in declarations:
        tool = _resolve_tool_declaration(declaration, owner=owner, warnings=warnings)
        if tool is None:
            continue
        name = getattr(tool, "__name__", None) or ""
        if name in seen:
            continue
        seen.add(name)
        tools.append(tool)
    return tools


def resolve_controller_capabilities(
    controller_config: dict[str, Any],
    *,
    owner: str,
    warnings: RuntimeWarnings,
):
    memories = _resolve_memories(controller_config.get("memories") or [], owner=owner, warnings=warnings)
    retrievers = _resolve_retrievers(controller_config.get("retrievers") or [], owner=owner, warnings=warnings)
    tools = resolve_agent_tools(controller_config.get("tools") or [], owner=owner, warnings=warnings)
    return tools, memories, retrievers


def _resolve_tool_declaration(
    declaration: dict[str, Any],
    *,
    owner: str,
    warnings: RuntimeWarnings,
) -> Callable[..., Any] | None:
    name = str(declaration.get("name") or "").strip()
    binding = str(declaration.get("binding") or "builtin").strip().lower()
    description = str(declaration.get("description") or "").strip()
    if not name:
        warnings.add(f"{owner}: encountered a tool declaration with empty name; skipped")
        return None
    if binding == "builtin":
        tool = BUILTIN_TOOL_REGISTRY.get(name)
        if tool is None:
            warnings.add(
                f"{owner}: builtin tool '{name}' is not supported by ClawCanvas runtime; "
                f"supported builtins are {sorted(BUILTIN_TOOL_REGISTRY.keys())}"
            )
            return None
        return tool
    if binding == "mcp":
        warnings.add(
            f"{owner}: tool '{name}' uses binding 'mcp' but ClawCanvas runtime has no MCP endpoint config for it yet"
        )
        return None
    if binding == "api":
        tool = _build_api_tool(name, description, owner=owner, warnings=warnings)
        if tool is None:
            return None
        return tool
    warnings.add(f"{owner}: tool '{name}' uses unsupported binding '{binding}' and was skipped")
    return None


def _resolve_memories(
    declarations: list[dict[str, Any]],
    *,
    owner: str,
    warnings: RuntimeWarnings,
):
    from masfactory.adapters.memory import HistoryMemory, VectorMemory
    from masfactory.utils.embedding import SimpleEmbedder

    memories = []
    embedder_factory = None
    for declaration in declarations:
        name = str(declaration.get("name") or "").strip()
        binding = str(declaration.get("binding") or "builtin").strip().lower()
        description = str(declaration.get("description") or "").strip()
        if not name:
            warnings.add(f"{owner}: encountered a memory declaration with empty name; skipped")
            continue
        if binding != "builtin":
            warnings.add(f"{owner}: memory '{name}' uses unsupported binding '{binding}' and was skipped")
            continue
        if name == "history_memory":
            memories.append(
                HistoryMemory(
                    top_k=_extract_int(description, "top_k", default=10),
                    memory_size=_extract_int(description, "memory_size", default=1000),
                    context_label=_extract_context_label(name, description, default="CONVERSATION_HISTORY"),
                )
            )
            continue
        if name == "vector_memory":
            if embedder_factory is None:
                embedder_factory = SimpleEmbedder().get_embedding_function()
            seed_docs = _extract_documents(name, description, warnings=warnings, owner=owner)
            memory = VectorMemory(
                embedding_function=embedder_factory,
                top_k=_extract_int(description, "top_k", default=8),
                query_threshold=_extract_float(description, "threshold", default=0.1),
                memory_size=max(len(seed_docs), _extract_int(description, "memory_size", default=20)),
                context_label=_extract_context_label(name, description, default="SEMANTIC_KNOWLEDGE"),
                passive=_extract_bool(description, "passive", default=True),
                active=_extract_bool(description, "active", default=False),
            )
            for index, text in enumerate(seed_docs, start=1):
                memory.insert(f"{name}_{index}", text)
            memories.append(memory)
            continue
        warnings.add(
            f"{owner}: builtin memory '{name}' is not supported; supported builtins are ['history_memory', 'vector_memory']"
        )
    return memories


def _resolve_retrievers(
    declarations: list[dict[str, Any]],
    *,
    owner: str,
    warnings: RuntimeWarnings,
):
    from masfactory.adapters.retrieval import FileSystemRetriever, SimpleKeywordRetriever, VectorRetriever
    from masfactory.utils.embedding import SimpleEmbedder

    retrievers = []
    embedder_factory = None
    for declaration in declarations:
        name = str(declaration.get("name") or "").strip()
        binding = str(declaration.get("binding") or "builtin").strip().lower()
        description = str(declaration.get("description") or "").strip()
        if not name:
            warnings.add(f"{owner}: encountered a retriever declaration with empty name; skipped")
            continue
        if binding != "builtin":
            warnings.add(f"{owner}: retriever '{name}' uses unsupported binding '{binding}' and was skipped")
            continue
        documents = _extract_documents(name, description, warnings=warnings, owner=owner)
        if name == "keyword_retriever":
            retrievers.append(
                SimpleKeywordRetriever(
                    _documents_to_mapping(name, documents),
                    context_label=_extract_context_label(name, description, default="KEYWORD_RETRIEVER"),
                    passive=_extract_bool(description, "passive", default=True),
                    active=_extract_bool(description, "active", default=False),
                )
            )
            continue
        if name == "vector_retriever":
            if embedder_factory is None:
                embedder_factory = SimpleEmbedder().get_embedding_function()
            retrievers.append(
                VectorRetriever(
                    _documents_to_mapping(name, documents),
                    embedding_function=embedder_factory,
                    similarity_threshold=_extract_float(description, "threshold", default=0.1),
                    context_label=_extract_context_label(name, description, default="VECTOR_RETRIEVER"),
                    passive=_extract_bool(description, "passive", default=True),
                    active=_extract_bool(description, "active", default=False),
                )
            )
            continue
        if name == "filesystem_retriever":
            docs_dir = _extract_setting(description, "docs_dir")
            if not docs_dir:
                warnings.add(f"{owner}: builtin retriever 'filesystem_retriever' requires docs_dir=<path> in description")
                continue
            docs_path = Path(docs_dir).expanduser()
            if not docs_path.is_absolute():
                docs_path = (Path.cwd() / docs_path).resolve()
            if embedder_factory is None:
                embedder_factory = SimpleEmbedder().get_embedding_function()
            retrievers.append(
                FileSystemRetriever(
                    docs_dir=docs_path,
                    embedding_function=embedder_factory,
                    file_extension=_extract_setting(description, "file_extension") or ".txt",
                    similarity_threshold=_extract_float(description, "threshold", default=0.1),
                    context_label=_extract_context_label(name, description, default="FILESYSTEM_RETRIEVER"),
                    passive=_extract_bool(description, "passive", default=True),
                    active=_extract_bool(description, "active", default=False),
                )
            )
            continue
        warnings.add(
            f"{owner}: builtin retriever '{name}' is not supported; supported builtins are "
            "['keyword_retriever', 'vector_retriever', 'filesystem_retriever']"
        )
    return retrievers


def merge_tool_declarations(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: Counter[tuple[str, str]] = Counter()
    for group in groups:
        for item in group or []:
            declaration = dict(item or {})
            name = str(declaration.get("name") or "").strip()
            binding = str(declaration.get("binding") or "").strip().lower()
            if not name:
                merged.append(declaration)
                continue
            token = (name, binding)
            if seen[token]:
                continue
            seen[token] += 1
            merged.append(declaration)
    return merged


def validate_tool_declarations(declarations: list[dict[str, Any]], *, owner: str) -> list[str]:
    warnings: list[str] = []
    collector = RuntimeWarnings(lambda message: warnings.append(message))
    for declaration in declarations:
        _resolve_tool_declaration(declaration, owner=owner, warnings=collector)
    return warnings


def validate_memory_declarations(declarations: list[dict[str, Any]], *, owner: str) -> list[str]:
    warnings: list[str] = []
    for declaration in declarations:
        name = str(declaration.get("name") or "").strip()
        binding = str(declaration.get("binding") or "builtin").strip().lower()
        description = str(declaration.get("description") or "").strip()
        if not name:
            warnings.append(f"{owner}: encountered a memory declaration with empty name; skipped")
            continue
        if binding != "builtin":
            warnings.append(f"{owner}: memory '{name}' uses unsupported binding '{binding}' and will not be bound")
            continue
        if name not in SUPPORTED_BUILTIN_MEMORIES:
            warnings.append(
                f"{owner}: builtin memory '{name}' is not supported; supported builtins are {sorted(SUPPORTED_BUILTIN_MEMORIES)}"
            )
            continue
        if name == "vector_memory":
            raw_docs = _extract_setting(description, "docs")
            if raw_docs is not None and not [item.strip() for item in raw_docs.split('||') if item.strip()]:
                warnings.append(f"{owner}: builtin memory '{name}' declared docs= but no valid seed content was found")
    return warnings


def validate_retriever_declarations(declarations: list[dict[str, Any]], *, owner: str) -> list[str]:
    warnings: list[str] = []
    for declaration in declarations:
        name = str(declaration.get("name") or "").strip()
        binding = str(declaration.get("binding") or "builtin").strip().lower()
        description = str(declaration.get("description") or "").strip()
        if not name:
            warnings.append(f"{owner}: encountered a retriever declaration with empty name; skipped")
            continue
        if binding != "builtin":
            warnings.append(f"{owner}: retriever '{name}' uses unsupported binding '{binding}' and will not be bound")
            continue
        if name not in SUPPORTED_BUILTIN_RETRIEVERS:
            warnings.append(
                f"{owner}: builtin retriever '{name}' is not supported; supported builtins are {sorted(SUPPORTED_BUILTIN_RETRIEVERS)}"
            )
            continue
        if name == "filesystem_retriever" and not _extract_setting(description, "docs_dir"):
            warnings.append(f"{owner}: builtin retriever 'filesystem_retriever' requires docs_dir=<path> in description")
    return warnings


def _extract_documents(name: str, description: str, *, warnings: RuntimeWarnings, owner: str) -> list[str]:
    raw = _extract_setting(description, "docs")
    if raw is None:
        return [description] if description else []
    parts = [item.strip() for item in raw.split("||") if item.strip()]
    if not parts and description:
        warnings.add(f"{owner}: capability '{name}' declared docs= but no valid document content was found")
    return parts


def _documents_to_mapping(prefix: str, documents: list[str]) -> dict[str, str]:
    if not documents:
        return {}
    return {f"{prefix}_{index}": text for index, text in enumerate(documents, start=1)}


def _extract_context_label(name: str, description: str, *, default: str) -> str:
    label = _extract_setting(description, "context_label")
    return label or default or name.upper()


def _extract_int(description: str, key: str, *, default: int) -> int:
    raw = _extract_setting(description, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _extract_float(description: str, key: str, *, default: float) -> float:
    raw = _extract_setting(description, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _extract_bool(description: str, key: str, *, default: bool) -> bool:
    raw = _extract_setting(description, key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _extract_setting(description: str, key: str) -> str | None:
    for chunk in str(description or "").splitlines():
        for piece in chunk.split(";"):
            piece = piece.strip()
            if not piece or "=" not in piece:
                continue
            current_key, value = piece.split("=", 1)
            if current_key.strip().lower() == key.lower():
                return value.strip()
    return None


def _build_api_tool(
    name: str,
    description: str,
    *,
    owner: str,
    warnings: RuntimeWarnings,
) -> Callable[..., Any] | None:
    try:
        import requests
    except ImportError:
        warnings.add(f"{owner}: tool '{name}' uses binding 'api' but Python package 'requests' is not installed")
        return None

    method = (_extract_setting(description, "method") or "POST").strip().upper()
    url = (_extract_setting(description, "url") or "").strip()
    timeout = _extract_float(description, "timeout", default=20.0)
    if not url:
        warnings.add(f"{owner}: api tool '{name}' requires url=<endpoint> in description")
        return None

    raw_headers = _extract_setting(description, "headers")
    raw_static_params = _extract_setting(description, "params")
    raw_static_body = _extract_setting(description, "body")
    response_mode = (_extract_setting(description, "response") or "json").strip().lower()

    static_headers = _parse_json_mapping(raw_headers, owner=owner, label=f"api tool '{name}' headers", warnings=warnings)
    static_params = _parse_json_mapping(raw_static_params, owner=owner, label=f"api tool '{name}' params", warnings=warnings)
    static_body = _parse_json_value(raw_static_body, owner=owner, label=f"api tool '{name}' body", warnings=warnings)

    def api_tool(**arguments):
        request_url = _render_api_template(url, arguments)
        headers = {key: _render_api_template(str(value), arguments) for key, value in static_headers.items()}
        params = {key: _render_api_template(str(value), arguments) for key, value in static_params.items()}
        payload = _render_json_payload(static_body, arguments)
        if payload is None and arguments:
            payload = dict(arguments)

        request_kwargs: dict[str, Any] = {
            "headers": headers or None,
            "params": params or None,
            "timeout": timeout,
        }
        if method in {"GET", "DELETE"}:
            if payload is not None and not params:
                request_kwargs["params"] = payload
        else:
            request_kwargs["json"] = payload

        response = requests.request(method, request_url, **request_kwargs)
        response.raise_for_status()
        if response_mode == "text":
            return {"status_code": response.status_code, "text": response.text}
        try:
            data = response.json()
        except ValueError:
            data = {"text": response.text}
        return {
            "status_code": response.status_code,
            "data": data,
        }

    api_tool.__name__ = f"api_{_safe_callable_name(name)}"
    api_tool.__doc__ = (
        f"HTTP API tool '{name}'. "
        "Configure description as semicolon-separated key=value entries, for example: "
        "method=POST; url=https://example.com/endpoint; headers={\"Authorization\":\"Bearer {token}\"}; "
        "body={\"query\":\"{query}\"}; response=json"
    )
    return api_tool


def _parse_json_mapping(raw: str | None, *, owner: str, label: str, warnings: RuntimeWarnings) -> dict[str, str]:
    if raw is None or not raw.strip():
        return {}
    parsed = _parse_json_value(raw, owner=owner, label=label, warnings=warnings)
    if isinstance(parsed, dict):
        return {str(key): str(value) for key, value in parsed.items()}
    warnings.add(f"{owner}: {label} must be a JSON object")
    return {}


def _parse_json_value(raw: str | None, *, owner: str, label: str, warnings: RuntimeWarnings) -> Any:
    if raw is None or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except Exception:
        warnings.add(f"{owner}: {label} must be valid JSON")
        return None


def _render_json_payload(payload: Any, arguments: dict[str, Any]) -> Any:
    if payload is None:
        return None
    if isinstance(payload, str):
        return _render_api_template(payload, arguments)
    if isinstance(payload, list):
        return [_render_json_payload(item, arguments) for item in payload]
    if isinstance(payload, dict):
        return {str(key): _render_json_payload(value, arguments) for key, value in payload.items()}
    return payload


def _render_api_template(template: str, arguments: dict[str, Any]) -> str:
    rendered = str(template)
    for key, value in arguments.items():
        rendered = rendered.replace("{" + str(key) + "}", str(value))
    return rendered


def _safe_callable_name(name: str) -> str:
    chars = []
    for char in str(name):
        if char.isalnum() or char == "_":
            chars.append(char.lower())
        else:
            chars.append("_")
    collapsed = "".join(chars).strip("_")
    return collapsed or "tool"
