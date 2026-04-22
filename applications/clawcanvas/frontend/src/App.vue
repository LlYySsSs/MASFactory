<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import CanvasBoard from './components/CanvasBoard.vue';
import InspectorPanel from './components/InspectorPanel.vue';
import KeyPoolPanel from './components/KeyPoolPanel.vue';
import LoopEditorModal from './components/LoopEditorModal.vue';
import MapEditor from './components/MapEditor.vue';
import { buildNodeTemplate, createDemoDocument, nextNodeId, normalizeLoopConfig } from './composables/useClawCanvas';

const API_ROOT = 'http://127.0.0.1:5000/api';

const documentRef = ref(createDemoDocument());
const selectedNodeId = ref('');
const selectedEdgeId = ref('');
const apiKey = ref('');
const baseUrl = ref('');
const modelName = ref('gpt-4o-mini');
const statusText = ref('Idle');
const validationSummary = ref(null);
const runResult = ref(null);
const warnings = ref([]);
const keyPool = ref({ keys: [], key_names: [], key_map: {} });
const loopEditorNodeId = ref('');

const selectedNode = computed(() =>
  documentRef.value.nodes.find((node) => node.id === selectedNodeId.value) || null
);

const nodesById = computed(() => {
  const map = new Map();
  for (const node of documentRef.value.nodes) {
    map.set(node.id, node);
  }
  return map;
});

const selectedLoopNode = computed(() =>
  documentRef.value.nodes.find((node) => node.id === loopEditorNodeId.value && node.type === 'loop') || null
);

function collectKeyPoolFromDocument(document) {
  const keyMap = new Map();

  function addKey(key, description = '', source = 'unknown', owner = 'workflow') {
    const normalizedKey = String(key || '').trim();
    if (!normalizedKey) return;
    const existing = keyMap.get(normalizedKey) || {
      key: normalizedKey,
      description: '',
      sources: [],
      owners: []
    };
    const normalizedDescription = String(description || '').trim();
    if (normalizedDescription && !existing.description) {
      existing.description = normalizedDescription;
    }
    if (source && !existing.sources.includes(source)) existing.sources.push(source);
    if (owner && !existing.owners.includes(owner)) existing.owners.push(owner);
    keyMap.set(normalizedKey, existing);
  }

  for (const [key, value] of Object.entries(document.inputs || {})) {
    addKey(key, value, 'document.inputs', 'workflow');
  }
  for (const [key, value] of Object.entries(document.attributes || {})) {
    addKey(key, value, 'document.attributes', 'workflow');
  }
  for (const [key, value] of Object.entries(document.key_descriptions || {})) {
    addKey(key, value, 'document.key_descriptions', 'workflow');
  }
  for (const edge of document.edges || []) {
    for (const [key, value] of Object.entries(edge.mapping || {})) {
      addKey(key, value, 'edge.mapping', edge.id);
    }
  }
  for (const node of document.nodes || []) {
    collectNodeConfigKeys(node.config || {}, node.id, addKey);
  }

  const keys = [...keyMap.values()].sort((a, b) => a.key.localeCompare(b.key));
  keyPool.value = {
    keys,
    key_names: keys.map((item) => item.key),
    key_map: Object.fromEntries(keys.map((item) => [item.key, item.description]))
  };
}

function collectNodeConfigKeys(config, owner, addKey) {
  for (const fieldName of ['pull_keys', 'push_keys', 'templates', 'static_outputs', 'pick_keys']) {
    for (const [key, value] of Object.entries(config[fieldName] || {})) {
      addKey(key, value, `node.${fieldName}`, owner);
    }
  }
  const terminateWhen = config.terminate_when || {};
  if (terminateWhen.key) {
    addKey(terminateWhen.key, 'Loop terminate condition key', 'node.terminate_when', owner);
  }
  for (const controllerEdge of config.controller_inputs || []) {
    for (const [key, value] of Object.entries(controllerEdge.mapping || {})) {
      addKey(key, value, 'node.controller_inputs', owner);
    }
  }
  for (const controllerEdge of config.controller_outputs || []) {
    for (const [key, value] of Object.entries(controllerEdge.mapping || {})) {
      addKey(key, value, 'node.controller_outputs', owner);
    }
  }
  const subgraph = config.subgraph || {};
  for (const edge of subgraph.edges || []) {
    for (const [key, value] of Object.entries(edge.mapping || {})) {
      addKey(key, value, 'node.subgraph.edge.mapping', `${owner}.${edge.id}`);
    }
  }
  for (const node of subgraph.nodes || []) {
    collectNodeConfigKeys(node.config || {}, `${owner}.${node.id}`, addKey);
  }
}

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
  collectKeyPoolFromDocument(documentRef.value);
  selectedNodeId.value = '';
  selectedEdgeId.value = '';
  validationSummary.value = null;
  runResult.value = null;
  warnings.value = [];
  statusText.value = 'Demo document restored';
}

function selectNode(nodeId) {
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = '';
}

function selectEdge(edgeId) {
  selectedEdgeId.value = edgeId;
  selectedNodeId.value = '';
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

function renameNode({ id, label }) {
  const node = documentRef.value.nodes.find((item) => item.id === id);
  if (!node) return;
  node.label = label;
  statusText.value = `Renamed ${id} to ${label}`;
}

function updateManifest(patch) {
  documentRef.value.manifest = {
    ...documentRef.value.manifest,
    ...patch
  };
}

function updateKeyPoolDescriptions(nextMap) {
  documentRef.value.key_descriptions = Object.fromEntries(
    Object.entries(nextMap || {})
      .map(([key, value]) => [String(key || '').trim(), String(value || '')])
      .filter(([key]) => key)
  );
  collectKeyPoolFromDocument(documentRef.value);
}

function renameKeyInObject(obj, oldKey, newKey) {
  const next = { ...(obj || {}) };
  if (!(oldKey in next) || !newKey || oldKey === newKey) return next;
  next[newKey] = next[oldKey];
  delete next[oldKey];
  return next;
}

function renamePlaceholders(text, oldKey, newKey) {
  if (typeof text !== 'string') return text;
  return text.replaceAll(`{${oldKey}}`, `{${newKey}}`);
}

function renameKeyInNodeConfig(config, oldKey, newKey) {
  const next = { ...(config || {}) };
  for (const fieldName of ['pull_keys', 'push_keys', 'templates', 'static_outputs', 'pick_keys']) {
    next[fieldName] = renameKeyInObject(next[fieldName], oldKey, newKey);
  }
  next.prompt_template = renamePlaceholders(next.prompt_template, oldKey, newKey);
  next.instructions = renamePlaceholders(next.instructions, oldKey, newKey);
  if (next.terminate_when?.key === oldKey) {
    next.terminate_when = { ...next.terminate_when, key: newKey };
  }
  next.controller_inputs = (next.controller_inputs || []).map((edge) => ({
    ...edge,
    mapping: renameKeyInObject(edge.mapping, oldKey, newKey)
  }));
  next.controller_outputs = (next.controller_outputs || []).map((edge) => ({
    ...edge,
    mapping: renameKeyInObject(edge.mapping, oldKey, newKey)
  }));
  if (next.subgraph) {
    next.subgraph = {
      ...next.subgraph,
      edges: (next.subgraph.edges || []).map((edge) => ({
        ...edge,
        mapping: renameKeyInObject(edge.mapping, oldKey, newKey)
      })),
      nodes: (next.subgraph.nodes || []).map((node) => ({
        ...node,
        config: renameKeyInNodeConfig(node.config, oldKey, newKey)
      }))
    };
  }
  return next;
}

function deriveLoopInputKeys(config) {
  const normalized = normalizeLoopConfig(config || {});
  const merged = {};
  for (const item of normalized.controller_inputs || []) {
    Object.assign(merged, item.mapping || {});
  }
  return merged;
}

function deriveLoopOutputKeys(config) {
  const normalized = normalizeLoopConfig(config || {});
  const merged = {};
  for (const item of normalized.controller_outputs || []) {
    Object.assign(merged, item.mapping || {});
  }
  return merged;
}

function renameWorkflowKey({ oldKey, newKey }) {
  const from = String(oldKey || '').trim();
  const to = String(newKey || '').trim();
  if (!from || !to || from === to) return;

  documentRef.value.inputs = renameKeyInObject(documentRef.value.inputs, from, to);
  documentRef.value.attributes = renameKeyInObject(documentRef.value.attributes, from, to);
  documentRef.value.key_descriptions = renameKeyInObject(documentRef.value.key_descriptions, from, to);
  documentRef.value.edges = documentRef.value.edges.map((edge) => ({
    ...edge,
    mapping: renameKeyInObject(edge.mapping, from, to)
  }));
  documentRef.value.nodes = documentRef.value.nodes.map((node) => ({
    ...node,
    config: renameKeyInNodeConfig(node.config, from, to)
  }));
  collectKeyPoolFromDocument(documentRef.value);
}

function deleteNode(nodeId) {
  documentRef.value.nodes = documentRef.value.nodes.filter((node) => node.id !== nodeId);
  documentRef.value.edges = documentRef.value.edges.filter(
    (edge) => edge.source !== nodeId && edge.target !== nodeId
  );
  if (selectedNodeId.value === nodeId) {
    selectedNodeId.value = '';
  }
  if (selectedEdgeId.value) {
    const edgeStillExists = documentRef.value.edges.some((edge) => edge.id === selectedEdgeId.value);
    if (!edgeStillExists) selectedEdgeId.value = '';
  }
  statusText.value = `Deleted node ${nodeId}`;
  if (loopEditorNodeId.value === nodeId) {
    loopEditorNodeId.value = '';
  }
}

function deleteEdge(edgeId) {
  documentRef.value.edges = documentRef.value.edges.filter((edge) => edge.id !== edgeId);
  if (selectedEdgeId.value === edgeId) {
    selectedEdgeId.value = '';
  }
  statusText.value = `Deleted edge ${edgeId}`;
}

function onGlobalKeyDown(event) {
  if (loopEditorNodeId.value) return;
  const target = event.target;
  const tagName = target?.tagName?.toLowerCase?.() || '';
  const isEditable =
    tagName === 'input' ||
    tagName === 'textarea' ||
    Boolean(target?.isContentEditable);
  if (isEditable) return;

  if (event.key !== 'Delete' && event.key !== 'Backspace') return;

  if (selectedEdgeId.value) {
    event.preventDefault();
    deleteEdge(selectedEdgeId.value);
    return;
  }

  if (selectedNodeId.value) {
    const node = documentRef.value.nodes.find((item) => item.id === selectedNodeId.value);
    if (!node || node.type === 'start' || node.type === 'end') return;
    event.preventDefault();
    deleteNode(selectedNodeId.value);
  }
}

onMounted(() => {
  window.addEventListener('keydown', onGlobalKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onGlobalKeyDown);
});

function updateEdgeMapping(edgeId, mapping) {
  const edge = documentRef.value.edges.find((item) => item.id === edgeId);
  if (!edge) return;
  edge.mapping = mapping;
  collectKeyPoolFromDocument(documentRef.value);
}

watch(
  documentRef,
  (nextDocument) => {
    collectKeyPoolFromDocument(nextDocument);
  },
  { deep: true }
);

function mappingSuggestionsForEdge(edge) {
  const sourceNode = nodesById.value.get(edge.source);
  const targetNode = nodesById.value.get(edge.target);
  const suggestions = new Map();

  for (const [key, value] of Object.entries(readNodeOutputKeys(sourceNode))) {
    suggestions.set(key, { key, value: String(value ?? '') });
  }

  for (const [key, value] of Object.entries(readNodeInputKeys(targetNode))) {
    if (!suggestions.has(key)) {
      suggestions.set(key, { key, value: String(value ?? '') });
    }
  }

  return [...suggestions.values()];
}

function readNodeInputKeys(node) {
  if (!node) return {};
  if (node.type === 'agent' || node.type === 'custom') return node.config.pull_keys || {};
  if (node.type === 'loop') {
    return deriveLoopInputKeys(node.config);
  }
  return {};
}

function readNodeOutputKeys(node) {
  if (!node) return {};
  if (node.type === 'agent' || node.type === 'custom') return node.config.push_keys || {};
  if (node.type === 'loop') {
    return deriveLoopOutputKeys(node.config);
  }
  return {};
}

function openLoopEditor(nodeId) {
  const node = documentRef.value.nodes.find((item) => item.id === nodeId && item.type === 'loop');
  if (!node) return;
  loopEditorNodeId.value = nodeId;
}

function updateLoopConfig({ id, config }) {
  updateNode({
    id,
    patch: {
      config
    }
  });
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
    if (data.key_pool) keyPool.value = data.key_pool;
    warnings.value = data.warnings || [];
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
    keyPool.value = data.key_pool || keyPool.value;
    statusText.value = 'Backend demo loaded';
  } catch (error) {
    statusText.value = error.message;
  }
}

collectKeyPoolFromDocument(documentRef.value);
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
        <div class="helper-text">Click one node handle, then click a compatible handle on another node to connect them.</div>
        <div v-for="edge in documentRef.edges" :key="edge.id" class="edge-card">
          <div class="edge-title">{{ edge.source }} -> {{ edge.target }}</div>
          <MapEditor
            :value="edge.mapping"
            key-label="Edge Key"
            value-label="Meaning"
            key-placeholder="message"
            value-placeholder="What this field carries"
            help="Edge mapping says which fields move across this connection."
            :suggestions="mappingSuggestionsForEdge(edge)"
            suggestion-title="From Connected Nodes"
            @update:value="updateEdgeMapping(edge.id, $event)"
          />
        </div>
      </section>

      <KeyPoolPanel
        :key-pool="keyPool"
        @update-key-pool="updateKeyPoolDescriptions"
        @rename-key="renameWorkflowKey"
      />
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
        :selected-edge-id="selectedEdgeId"
        @select-node="selectNode"
        @select-edge="selectEdge"
        @move-node="moveNode"
        @create-edge="createEdge"
        @rename-node="renameNode"
        @open-loop="openLoopEditor"
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
        :document="documentRef"
        :key-pool="keyPool"
        @update-node="updateNode"
        @update-manifest="updateManifest"
        @delete-node="deleteNode"
        @open-loop-editor="openLoopEditor"
      />
    </aside>

    <LoopEditorModal
      v-if="selectedLoopNode"
      :loop-node="selectedLoopNode"
      :key-pool="keyPool"
      @close="loopEditorNodeId = ''"
      @rename-loop="renameNode"
      @update-loop-config="updateLoopConfig"
    />
  </div>
</template>
