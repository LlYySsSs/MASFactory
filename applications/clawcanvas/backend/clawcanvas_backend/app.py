from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

try:
    from flask import Flask, jsonify, request
except ImportError:  # pragma: no cover
    Flask = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]

try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    CORS = None  # type: ignore[assignment]

from .compiler import compile_document_to_graph
from .key_pool import collect_document_key_pool, rename_document_key
from .schema import build_demo_document, parse_document
from .skill_packager import export_skill_package
from .validation import analyze_document


def _exception_chain(err: Exception) -> list[dict[str, str]]:
    chain: list[dict[str, str]] = []
    current: Exception | None = err
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(
            {
                "type": current.__class__.__name__,
                "message": str(current),
            }
        )
        next_exc = current.__cause__ or current.__context__
        current = next_exc if isinstance(next_exc, Exception) else None
    return chain


def _unwrap_retry_error(err: Exception) -> Exception | None:
    last_attempt = getattr(err, "last_attempt", None)
    if last_attempt is None or not hasattr(last_attempt, "exception"):
        return None
    try:
        unwrapped = last_attempt.exception()
    except Exception:
        return None
    return unwrapped if isinstance(unwrapped, Exception) else None


def _serialize_exception(err: Exception) -> dict[str, Any]:
    root = _unwrap_retry_error(err) or err
    chain = _exception_chain(root if root is not err else err)
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))

    payload: dict[str, Any] = {
        "error": str(err),
        "error_type": err.__class__.__name__,
        "root_cause": str(root),
        "root_cause_type": root.__class__.__name__,
        "cause_chain": chain,
        "traceback": tb[-12000:],
    }

    if root is not err:
        payload["retry_error"] = {
            "message": str(err),
            "root_cause": str(root),
            "root_cause_type": root.__class__.__name__,
        }

    return payload


def create_app() -> "Flask":
    if Flask is None:
        raise RuntimeError("Flask is not installed. Run `pip install -r requirements.txt` first.")

    app = Flask(__name__)
    if CORS is not None:
        CORS(app)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "clawcanvas-backend"})

    @app.get("/api/demo")
    def demo():
        document = build_demo_document()
        return jsonify({"document": document.to_dict(), "key_pool": collect_document_key_pool(document)})

    @app.post("/api/validate")
    def validate_document_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        analysis = analyze_document(document)
        return jsonify(
            {
                "ok": True,
                "document": document.to_dict(),
                "key_pool": analysis["key_pool"],
                "warnings": analysis["warnings"],
                "summary": {
                    "node_count": len(document.nodes),
                    "edge_count": len(document.edges),
                    "warning_count": len(analysis["warnings"]),
                },
            }
        )

    @app.post("/api/key-pool/rename")
    def rename_key_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        old_key = str(payload.get("oldKey") or "")
        new_key = str(payload.get("newKey") or "")
        updated = rename_document_key(document, old_key, new_key)
        return jsonify(
            {
                "ok": True,
                "document": updated.to_dict(),
                "key_pool": collect_document_key_pool(updated),
            }
        )

    @app.post("/api/run")
    def run_document_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        runtime = payload.get("runtime") or {}
        api_key = str(runtime.get("apiKey") or "").strip()
        if not api_key:
            return jsonify({"ok": False, "error": "runtime.apiKey is required"}), 400

        model_name = str(runtime.get("modelName") or "gpt-4o-mini")
        base_url = str(runtime.get("baseUrl") or "").strip() or None
        graph, warnings = compile_document_to_graph(
            document,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
        )
        output, attributes = graph.invoke(dict(document.inputs), attributes=dict(document.attributes))
        return jsonify(
            {
                "ok": True,
                "output": output,
                "attributes": attributes,
                "warnings": warnings.items,
                "runtime": {
                    "model_name": model_name,
                    "base_url": base_url,
                },
            }
        )

    @app.post("/api/export-skill")
    def export_skill_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        run_output = dict(payload.get("runOutput") or {})
        warnings = list(payload.get("warnings") or [])
        export_format = str(payload.get("format") or "json").lower()

        if export_format not in {"json", "markdown", "zip"}:
            return jsonify({"ok": False, "error": f"Unsupported format: {export_format}"}), 400

        export_root = Path(__file__).resolve().parents[2] / "exports"
        result = export_skill_package(
            document,
            export_root=export_root,
            run_output=run_output,
            warnings=warnings,
            format=export_format,
        )
        return jsonify({"ok": True, **result})

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        status = getattr(err, "code", None)
        if status is None:
            status = 400 if isinstance(err, (ValueError, KeyError)) else 500
        return jsonify({"ok": False, **_serialize_exception(err)}), status

    return app


if __name__ == "__main__":  # pragma: no cover
    create_app().run(host="127.0.0.1", port=5000, debug=True)
