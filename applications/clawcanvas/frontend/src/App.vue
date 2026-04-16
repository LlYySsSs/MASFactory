<script setup>
import { computed, ref } from 'vue';
import CanvasBoard from './components/CanvasBoard.vue';
import InspectorPanel from './components/InspectorPanel.vue';
import { buildNodeTemplate, createDemoDocument, nextNodeId } from './composables/useClawCanvas';

const API_ROOT = 'http://127.0.0.1:5000/api';

const documentRef = ref(createDemoDocument());
const selectedNodeId = ref('');
const apiKey = ref('');
const baseUrl = ref('');
const modelName = ref('gpt-4o-mini');
const statusText = ref('Idle');
const validationSummary = ref(null);
const runResult = ref(null);
const warnings = ref([]);

const selectedNode = computed(() =>
  documentRef.value.nodes.find((node) => node.id === selectedNodeId.value) || null
);

function addNode(type) {
  const id = nextNodeId(documentRef.value, type);
  const node = buildNodeTemplate(type, id);
  node.position = {
    x: 220 + documentRef.value.nodes.length * 18,
    y: 120 + documentRef.value.nodes.length * 22
  };
  documentRef.value.nodes.push(node);
  selectedNodeId.value = id;
  statusText.value = `Added ${type} node ${id}`;
}

function resetDemo() {
  documentRef.value = createDemoDocument();
  selectedNodeId.value = '';
  validationSummary.value = null;
  runResult.value = null;
  warnings.value = [];
  statusText.value = 'Demo document restored';
}

function selectNode(nodeId) {
  selectedNodeId.value = nodeId;
}

function moveNode({ id, position }) {
  const node = documentRef.value.nodes.find((item) => item.id === id);
  if (!node) return;
  node.position = position;
}

function createEdge({ source, target }) {
  const sourceNode = documentRef.value.nodes.find((node) => node.id === source);
  const targetNode = documentRef.value.nodes.find((node) => node.id === target);
  if (!sourceNode || !targetNode) return;
  if (documentRef.value.edges.some((edge) => edge.source === source && edge.target === target)) {
    statusText.value = `Edge ${source} -> ${target} already exists`;
    return;
  }
  const id = `edge_${documentRef.value.edges.length + 1}`;
  documentRef.value.edges.push({
    id,
    source,
    target,
    mapping: defaultEdgeMapping(sourceNode.type, targetNode.type)
  });
  statusText.value = `Created edge ${source} -> ${target}`;
}

function defaultEdgeMapping(sourceType, targetType) {
  if (targetType === 'agent') {
    return { message: 'message' };
  }
  if (targetType === 'custom') {
    return { message: 'message' };
  }
  if (targetType === 'loop') {
    return { message: 'loop seed' };
  }
  if (targetType === 'end') {
    return sourceType === 'loop' ? { message: 'loop result' } : { message: 'result' };
  }
  return { message: 'message' };
}

function updateNode({ id, patch }) {
  const index = documentRef.value.nodes.findIndex((item) => item.id === id);
  if (index === -1) return;
  const current = documentRef.value.nodes[index];
  documentRef.value.nodes[index] = {
    ...current,
    ...patch,
    config: patch.config ? { ...current.config, ...patch.config } : current.config
  };
}

function updateManifest(patch) {
  documentRef.value.manifest = {
    ...documentRef.value.manifest,
    ...patch
  };
}

function deleteNode(nodeId) {
  documentRef.value.nodes = documentRef.value.nodes.filter((node) => node.id !== nodeId);
  documentRef.value.edges = documentRef.value.edges.filter(
    (edge) => edge.source !== nodeId && edge.target !== nodeId
  );
  if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = '';
  }
  statusText.value = `Deleted node ${nodeId}`;
}

function updateEdgeMapping(edgeId, raw) {
  const edge = documentRef.value.edges.find((item) => item.id === edgeId);
  if (!edge) return;
  try {
    edge.mapping = raw ? JSON.parse(raw) : {};
  } catch {
    statusText.value = `Invalid JSON mapping for ${edgeId}`;
  }
}

async function fetchApi(path, payload) {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function validateWorkflow() {
  statusText.value = 'Validating workflow...';
  try {
    const data = await fetchApi('/validate', { document: documentRef.value });
    validationSummary.value = data.summary;
    statusText.value = 'Validation passed';
  } catch (error) {
    statusText.value = error.message;
  }
}

async function runWorkflow() {
  statusText.value = 'Running workflow...';
  try {
    const data = await fetchApi('/run', {
      document: documentRef.value,
      runtime: {
        apiKey: apiKey.value,
        baseUrl: baseUrl.value,
        modelName: modelName.value
      }
    });
    runResult.value = data.output;
    warnings.value = data.warnings || [];
    statusText.value = 'Workflow run completed';
  } catch (error) {
    statusText.value = error.message;
  }
}

async function exportSkill() {
  statusText.value = 'Exporting skill package...';
  try {
    const data = await fetchApi('/export-skill', {
      document: documentRef.value,
      runOutput: runResult.value || {},
      warnings: warnings.value
    });
    statusText.value = `Skill exported to ${data.export_dir}`;
  } catch (error) {
    statusText.value = error.message;
  }
}

async function loadDemoFromBackend() {
  statusText.value = 'Loading backend demo...';
  try {
    const response = await fetch(`${API_ROOT}/demo`);
    const data = await response.json();
    documentRef.value = data.document;
    statusText.value = 'Backend demo loaded';
  } catch (error) {
    statusText.value = error.message;
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="left-panel">
      <div class="brand">
        <div class="eyebrow">MASFactory Application</div>
        <h1>ClawCanvas</h1>
        <p>Design workflows, validate them, and package them as skills.</p>
      </div>

      <section class="tool-group">
        <div class="group-title">Canvas</div>
        <button type="button" @click="addNode('agent')">Add Agent</button>
        <button type="button" @click="addNode('custom')">Add Custom</button>
        <button type="button" @click="addNode('loop')">Add Loop</button>
        <button type="button" class="ghost" @click="resetDemo">Reset Demo</button>
        <button type="button" class="ghost" @click="loadDemoFromBackend">Load Backend Demo</button>
      </section>

      <section class="tool-group">
        <div class="group-title">Runtime</div>
        <label>
          <span>API Key</span>
          <input v-model="apiKey" type="password" placeholder="sk-..." />
        </label>
        <label>
          <span>Base URL</span>
          <input v-model="baseUrl" placeholder="Optional OpenAI-compatible endpoint" />
        </label>
        <label>
          <span>Model Name</span>
          <input v-model="modelName" placeholder="gpt-4o-mini" />
        </label>
      </section>

      <section class="tool-group">
        <div class="group-title">Actions</div>
        <button type="button" @click="validateWorkflow">Validate</button>
        <button type="button" @click="runWorkflow">Run Test</button>
        <button type="button" @click="exportSkill">Export Skill</button>
      </section>

      <section class="tool-group">
        <div class="group-title">Edges</div>
        <div class="helper-text">Drag from a node's right handle to another node's left handle to connect them.</div>
        <div v-for="edge in documentRef.edges" :key="edge.id" class="edge-card">
          <div class="edge-title">{{ edge.source }} -> {{ edge.target }}</div>
          <textarea
            :value="JSON.stringify(edge.mapping, null, 2)"
            @input="updateEdgeMapping(edge.id, $event.target.value)"
          />
        </div>
      </section>
    </aside>

    <main class="workspace">
      <header class="workspace-header">
        <div>
          <div class="eyebrow">Workflow</div>
          <h2>{{ documentRef.name }}</h2>
          <p>{{ documentRef.description }}</p>
        </div>
        <div class="status-card">
          <div class="status-label">Status</div>
          <div class="status-value">{{ statusText }}</div>
        </div>
      </header>

      <CanvasBoard
        :nodes="documentRef.nodes"
        :edges="documentRef.edges"
        :selected-node-id="selectedNodeId"
        @select-node="selectNode"
        @move-node="moveNode"
        @create-edge="createEdge"
        @status="statusText = $event"
      />

      <section class="console-grid">
        <article class="console-card">
          <div class="console-title">Validation</div>
          <pre>{{ validationSummary ? JSON.stringify(validationSummary, null, 2) : 'Not validated yet.' }}</pre>
        </article>
        <article class="console-card">
          <div class="console-title">Run Output</div>
          <pre>{{ runResult ? JSON.stringify(runResult, null, 2) : 'No run result yet.' }}</pre>
        </article>
        <article class="console-card">
          <div class="console-title">Warnings</div>
          <pre>{{ warnings.length ? JSON.stringify(warnings, null, 2) : 'No warnings.' }}</pre>
        </article>
      </section>
    </main>

    <aside class="right-panel">
      <InspectorPanel
        :selected-node="selectedNode"
        :manifest="documentRef.manifest"
        @update-node="updateNode"
        @update-manifest="updateManifest"
        @delete-node="deleteNode"
      />
    </aside>
  </div>
</template>
