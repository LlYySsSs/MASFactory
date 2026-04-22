# ClawCanvas

ClawCanvas is a MASFactory-based skill studio for designing, testing, and packaging workflows as reusable skills.

The first MVP in this directory focuses on four capabilities:

- build a workflow on a web canvas
- validate the workflow structure before execution
- execute supported nodes through MASFactory with a user-supplied API key
- export the workflow plus skill metadata as a publishable skill package

## Layout

```text
applications/clawcanvas/
├── backend/
│   ├── clawcanvas_backend/
│   │   ├── app.py
│   │   ├── compiler.py
│   │   ├── schema.py
│   │   ├── skill_packager.py
│   │   └── __init__.py
│   ├── requirements.txt
│   └── tests/
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
```

## MVP Scope

Currently supported runtime node types:

- `start`
- `agent`
- `custom`
- `loop`
- `end`

Current runtime constraints:

- graph must be a DAG
- exactly one `start` and one `end`
- supported tool execution is runtime-bound for `builtin` tools and configured `api` tools; `mcp` entries still need an external connector layer
- knowledge and behavior rules are compiled into agent prompt context, not yet into dedicated retrievers or MCP-backed tools
- `custom` nodes currently support built-in transform modes: `passthrough`, `template`, `set`, `pick`
- `loop` nodes are compiled into subgraph-based MASFactory `Loop` nodes with explicit controller inputs and controller outputs

## Backend

The backend is a Flask application that exposes:

- `GET /api/health`
- `GET /api/demo`
- `POST /api/validate`
- `POST /api/run`
- `POST /api/export-skill`

Install app-specific dependencies:

```bash
cd /local/lys/MASFactory
pip install -e .

cd applications/clawcanvas/backend
pip install -r requirements.txt
```

Run the backend:

```bash
python -m clawcanvas_backend.app
```

## Frontend

The frontend is a Vue + Vite application with a draggable node canvas.

Environment requirement: Node.js `>= 18` is strongly recommended. The current Vite toolchain will not run reliably on Node 12.

Install dependencies:

```bash
cd applications/clawcanvas/frontend
npm install
```

Run locally:

```bash
npm run dev
```

The frontend expects the backend to be available at `http://127.0.0.1:5000`.
