from __future__ import annotations

from pathlib import Path

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
from .schema import build_demo_document, parse_document
from .skill_packager import export_skill_package


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
        return jsonify({"document": build_demo_document().to_dict()})

    @app.post("/api/validate")
    def validate_document_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        return jsonify(
            {
                "ok": True,
                "document": document.to_dict(),
                "summary": {
                    "node_count": len(document.nodes),
                    "edge_count": len(document.edges),
                },
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
            }
        )

    @app.post("/api/export-skill")
    def export_skill_route():
        payload = request.get_json(force=True) or {}
        document = parse_document(payload.get("document") or payload)
        run_output = dict(payload.get("runOutput") or {})
        warnings = list(payload.get("warnings") or [])
        export_root = Path(__file__).resolve().parents[2] / "exports"
        result = export_skill_package(
            document,
            export_root=export_root,
            run_output=run_output,
            warnings=warnings,
        )
        return jsonify({"ok": True, **result})

    @app.errorhandler(Exception)
    def handle_exception(err: Exception):
        status = getattr(err, "code", 500)
        return jsonify({"ok": False, "error": str(err)}), status

    return app


if __name__ == "__main__":  # pragma: no cover
    create_app().run(host="127.0.0.1", port=5000, debug=True)
