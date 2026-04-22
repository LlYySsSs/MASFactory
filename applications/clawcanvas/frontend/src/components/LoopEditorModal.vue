<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import CanvasBoard from './CanvasBoard.vue';
import LoopNodeInspector from './LoopNodeInspector.vue';
import MapEditor from './MapEditor.vue';
import ObjectListEditor from './ObjectListEditor.vue';
import { buildNodeTemplate, nextNodeId, normalizeLoopConfig } from '../composables/useClawCanvas';

const CONTROLLER_IN_ID = '__controller_in__';
const CONTROLLER_OUT_ID = '__controller_out__';

const props = defineProps({
  loopNode: { type: Object, required: true },
  keyPool: { type: Object, required: true }
});

const emit = defineEmits(['close', 'update-loop-config', 'rename-loop']);

const selectedNodeId = ref('');
const selectedEdgeId = ref('');
const nestedLoopId = ref('');

const controllerCapabilityFields = [
  { key: 'name', label: 'Name', placeholder: 'controller_memory' },
  { key: 'binding', label: 'Binding', placeholder: 'builtin / mcp / custom' },
  { key: 'description', label: 'Description', placeholder: 'What this capability is for', multiline: true }
];

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const loopConfig = computed(() => normalizeLoopConfig(props.loopNode.config || {}));
const innerDocument = computed(() => ({
  nodes: loopConfig.value.subgraph.nodes || [],
  edges: [
    ...(loopConfig.value.controller_inputs || []).map((item) => ({
      id: `controller_in:${item.id}`,
      source: CONTROLLER_IN_ID,
      target: item.target,
      mapping: item.mapping || {}
    })),
    ...(loopConfig.value.subgraph.edges || []),
    ...(loopConfig.value.controller_outputs || []).map((item) => ({
      id: `controller_out:${item.id}`,
      source: item.source,
      target: CONTROLLER_OUT_ID,
      mapping: item.mapping || {}
    }))
  ]
}));

const canvasNodes = computed(() => [
  {
    id: CONTROLLER_IN_ID,
    type: 'start',
    label: 'Controller In',
    position: loopConfig.value.controller_layout?.input_position || { x: 40, y: 220 },
    meta: {
      renamable: false,
      handleMode: { left: 'disabled', right: 'output' },
      displayType: 'controller'
    }
  },
  ...(loopConfig.value.subgraph.nodes || []),
  {
    id: CONTROLLER_OUT_ID,
    type: 'end',
    label: 'Controller Out',
    position: loopConfig.value.controller_layout?.output_position || { x: 980, y: 220 },
    meta: {
      renamable: false,
      handleMode: { left: 'input', right: 'disabled' },
      displayType: 'controller'
    }
  }
]);

const selectedNode = computed(() =>
  (loopConfig.value.subgraph.nodes || []).find((node) => node.id === selectedNodeId.value) || null
);

const selectedEdge = computed(() =>
  innerDocument.value.edges.find((edge) => edge.id === selectedEdgeId.value) || null
);

const nestedLoopNode = computed(() =>
  (loopConfig.value.subgraph.nodes || []).find((node) => node.id === nestedLoopId.value) || null
);

const innerNodeOptions = computed(() =>
  (loopConfig.value.subgraph.nodes || []).map((node) => ({
    id: node.id,
    label: `${node.label} (${node.id})`
  }))
);

const loopWarnings = computed(() => {
  const warnings = [];
  const controllerInputs = loopConfig.value.controller_inputs || [];
  const controllerOutputs = loopConfig.value.controller_outputs || [];
  const terminate = loopConfig.value.terminate_when || {};

  if (!controllerInputs.length) {
    warnings.push('Loop has no controller inputs, so outer workflow data never enters the inner graph.');
  }
  if (!controllerOutputs.length) {
    warnings.push('Loop has no controller outputs, so no inner result can return to the outer workflow.');
  }

  const producedKeys = new Set(
    controllerOutputs.flatMap((item) => Object.keys(item.mapping || {})).map((key) => String(key).trim()).filter(Boolean)
  );
  if ((terminate.mode || 'never') !== 'never' && terminate.key && !producedKeys.has(String(terminate.key))) {
    warnings.push(`Terminate key "${terminate.key}" is not present in any controller output mapping.`);
  }

  const outgoing = new Map();
  for (const node of loopConfig.value.subgraph.nodes || []) {
    outgoing.set(node.id, new Set());
  }
  for (const edge of loopConfig.value.subgraph.edges || []) {
    if (outgoing.has(edge.source) && outgoing.has(edge.target)) {
      outgoing.get(edge.source).add(edge.target);
    }
  }
  const reachable = new Set();
  const stack = controllerInputs.map((item) => item.target).filter((item) => outgoing.has(item));
  while (stack.length) {
    const current = stack.pop();
    if (reachable.has(current)) continue;
    reachable.add(current);
    for (const next of outgoing.get(current) || []) {
      stack.push(next);
    }
  }
  for (const item of controllerOutputs) {
    if (item.source && !reachable.has(item.source)) {
      warnings.push(`Controller output source "${item.source}" is not reachable from any controller input target.`);
    }
  }

  return warnings;
});

const internalOnlyKeys = computed(() => {
  const produced = new Set(
    (loopConfig.value.controller_outputs || [])
      .flatMap((item) => Object.keys(item.mapping || {}))
      .map((key) => String(key).trim())
      .filter(Boolean)
  );
  const inner = new Set();
  for (const node of loopConfig.value.subgraph.nodes || []) {
    for (const key of Object.keys(node.config?.push_keys || {})) {
      if (String(key).trim()) inner.add(String(key).trim());
    }
  }
  return [...inner].filter((key) => !produced.has(key)).sort();
});

function setLoopConfig(nextConfig) {
  emit('update-loop-config', {
    id: props.loopNode.id,
    config: nextConfig
  });
}

function selectNode(nodeId) {
  selectedNodeId.value = nodeId;
  selectedEdgeId.value = '';
}

function selectEdge(edgeId) {
  selectedEdgeId.value = edgeId;
  selectedNodeId.value = '';
}

function updateLoopField(field, value) {
  const next = clone(loopConfig.value);
  next[field] = value;
  setLoopConfig(next);
}

function updateTerminateField(field, value) {
  const next = clone(loopConfig.value);
  next.terminate_when = { ...(next.terminate_when || {}), [field]: value };
  setLoopConfig(next);
}

function updateControllerField(field, value) {
  const next = clone(loopConfig.value);
  next.controller = { ...(next.controller || {}), [field]: value };
  setLoopConfig(next);
}

function updateControllerModelField(field, value) {
  const next = clone(loopConfig.value);
  next.controller = {
    ...(next.controller || {}),
    model_settings: {
      ...(next.controller?.model_settings || {}),
      [field]: value
    }
  };
  setLoopConfig(next);
}

function addInnerNode(type) {
  const next = clone(loopConfig.value);
  const id = nextNodeId({ nodes: next.subgraph.nodes || [] }, type);
  const node = buildNodeTemplate(type, id);
  node.position = {
    x: 240 + (next.subgraph.nodes || []).length * 26,
    y: 120 + (next.subgraph.nodes || []).length * 24
  };
  next.subgraph.nodes.push(node);
  setLoopConfig(next);
  selectedNodeId.value = id;
  selectedEdgeId.value = '';
}

function updateInnerNode({ id, patch }) {
  const next = clone(loopConfig.value);
  const index = next.subgraph.nodes.findIndex((node) => node.id === id);
  if (index === -1) return;
  const current = next.subgraph.nodes[index];
  next.subgraph.nodes[index] = {
    ...current,
    ...patch,
    config: patch.config ? { ...current.config, ...patch.config } : current.config
  };
  setLoopConfig(next);
}

function renameInnerNode({ id, label }) {
  const next = clone(loopConfig.value);
  const node = next.subgraph.nodes.find((item) => item.id === id);
  if (!node) return;
  node.label = label;
  setLoopConfig(next);
}

function moveInnerNode({ id, position }) {
  const next = clone(loopConfig.value);
  next.controller_layout = next.controller_layout || {
    input_position: { x: 40, y: 220 },
    output_position: { x: 980, y: 220 }
  };
  if (id === CONTROLLER_IN_ID) {
    next.controller_layout.input_position = position;
    setLoopConfig(next);
    return;
  }
  if (id === CONTROLLER_OUT_ID) {
    next.controller_layout.output_position = position;
    setLoopConfig(next);
    return;
  }
  const node = next.subgraph.nodes.find((item) => item.id === id);
  if (!node) return;
  node.position = position;
  setLoopConfig(next);
}

function deleteInnerNode(nodeId) {
  const next = clone(loopConfig.value);
  next.subgraph.nodes = next.subgraph.nodes.filter((node) => node.id !== nodeId);
  next.subgraph.edges = next.subgraph.edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
  next.controller_inputs = next.controller_inputs.filter((edge) => edge.target !== nodeId);
  next.controller_outputs = next.controller_outputs.filter((edge) => edge.source !== nodeId);
  setLoopConfig(next);
  if (selectedNodeId.value === nodeId) selectedNodeId.value = '';
}

function deleteEdge(edgeId) {
  const next = clone(loopConfig.value);
  if (edgeId.startsWith('controller_in:')) {
    const rawId = edgeId.slice('controller_in:'.length);
    next.controller_inputs = next.controller_inputs.filter((edge) => edge.id !== rawId);
  } else if (edgeId.startsWith('controller_out:')) {
    const rawId = edgeId.slice('controller_out:'.length);
    next.controller_outputs = next.controller_outputs.filter((edge) => edge.id !== rawId);
  } else {
    next.subgraph.edges = next.subgraph.edges.filter((edge) => edge.id !== edgeId);
  }
  setLoopConfig(next);
  if (selectedEdgeId.value === edgeId) selectedEdgeId.value = '';
}

function createEdge({ source, target }) {
  if (source === CONTROLLER_OUT_ID || target === CONTROLLER_IN_ID) return;
  const next = clone(loopConfig.value);
  if (source === CONTROLLER_IN_ID && target !== CONTROLLER_OUT_ID) {
    next.controller_inputs.push({
      id: `controller_in_${next.controller_inputs.length + 1}`,
      target,
      mapping: { message: 'Loop input' }
    });
    setLoopConfig(next);
    return;
  }
  if (target === CONTROLLER_OUT_ID && source !== CONTROLLER_IN_ID) {
    next.controller_outputs.push({
      id: `controller_out_${next.controller_outputs.length + 1}`,
      source,
      mapping: { message: 'Loop output' }
    });
    setLoopConfig(next);
    return;
  }
  if (source !== CONTROLLER_IN_ID && target !== CONTROLLER_OUT_ID) {
    if (next.subgraph.edges.some((edge) => edge.source === source && edge.target === target)) return;
    next.subgraph.edges.push({
      id: `inner_edge_${next.subgraph.edges.length + 1}`,
      source,
      target,
      mapping: { message: 'message' }
    });
    setLoopConfig(next);
  }
}

function updateEdgeMapping(edgeId, mapping) {
  const next = clone(loopConfig.value);
  if (edgeId.startsWith('controller_in:')) {
    const rawId = edgeId.slice('controller_in:'.length);
    const edge = next.controller_inputs.find((item) => item.id === rawId);
    if (!edge) return;
    edge.mapping = mapping;
  } else if (edgeId.startsWith('controller_out:')) {
    const rawId = edgeId.slice('controller_out:'.length);
    const edge = next.controller_outputs.find((item) => item.id === rawId);
    if (!edge) return;
    edge.mapping = mapping;
  } else {
    const edge = next.subgraph.edges.find((item) => item.id === edgeId);
    if (!edge) return;
    edge.mapping = mapping;
  }
  setLoopConfig(next);
}

function controllerDisplay(edge) {
  if (!edge) return '';
  if (edge.id.startsWith('controller_in:')) return `Controller In -> ${edge.target}`;
  if (edge.id.startsWith('controller_out:')) return `${edge.source} -> Controller Out`;
  return `${edge.source} -> ${edge.target}`;
}

function mappingSuggestionsForSelectedEdge() {
  if (!selectedEdge.value) return [];
  if (selectedEdge.value.id.startsWith('controller_in:')) {
    const target = (loopConfig.value.subgraph.nodes || []).find((node) => node.id === selectedEdge.value.target);
    return mergeSuggestions(mappingSuggestions(props.keyPool.key_map || {}), mappingSuggestions(target?.config?.pull_keys || {}));
  }
  if (selectedEdge.value.id.startsWith('controller_out:')) {
    const source = (loopConfig.value.subgraph.nodes || []).find((node) => node.id === selectedEdge.value.source);
    return mergeSuggestions(mappingSuggestions(source?.config?.push_keys || {}), mappingSuggestions(props.keyPool.key_map || {}));
  }
  const source = (loopConfig.value.subgraph.nodes || []).find((node) => node.id === selectedEdge.value.source);
  const target = (loopConfig.value.subgraph.nodes || []).find((node) => node.id === selectedEdge.value.target);
  return mergeSuggestions(mappingSuggestions(source?.config?.push_keys || {}), mappingSuggestions(target?.config?.pull_keys || {}));
}

function mappingSuggestions(raw) {
  return Object.entries(raw || {}).map(([key, value]) => ({ key, value: String(value ?? '') }));
}

function mergeSuggestions(...groups) {
  const map = new Map();
  for (const group of groups) {
    for (const item of group || []) {
      const key = String(item?.key || '').trim();
      if (!key) continue;
      if (!map.has(key)) map.set(key, { key, value: String(item?.value || '') });
    }
  }
  return [...map.values()];
}

function openNestedLoop(nodeId) {
  nestedLoopId.value = nodeId;
}

function updateNestedLoopConfig(payload) {
  const next = clone(loopConfig.value);
  const index = next.subgraph.nodes.findIndex((node) => node.id === payload.id);
  if (index === -1) return;
  next.subgraph.nodes[index] = {
    ...next.subgraph.nodes[index],
    config: payload.config
  };
  setLoopConfig(next);
}

function addControllerInput() {
  const target = loopConfig.value.subgraph.nodes?.[0]?.id || '';
  if (!target) return;
  const next = clone(loopConfig.value);
  next.controller_inputs.push({
    id: `controller_in_${next.controller_inputs.length + 1}`,
    target,
    mapping: { message: 'Loop input' }
  });
  setLoopConfig(next);
}

function addControllerOutput() {
  const source = loopConfig.value.subgraph.nodes?.[0]?.id || '';
  if (!source) return;
  const next = clone(loopConfig.value);
  next.controller_outputs.push({
    id: `controller_out_${next.controller_outputs.length + 1}`,
    source,
    mapping: { message: 'Loop output' }
  });
  setLoopConfig(next);
}

function updateControllerInputTarget(id, target) {
  const next = clone(loopConfig.value);
  const edge = next.controller_inputs.find((item) => item.id === id);
  if (!edge) return;
  edge.target = target;
  setLoopConfig(next);
}

function updateControllerOutputSource(id, source) {
  const next = clone(loopConfig.value);
  const edge = next.controller_outputs.find((item) => item.id === id);
  if (!edge) return;
  edge.source = source;
  setLoopConfig(next);
}

function updateControllerInputMapping(id, mapping) {
  const next = clone(loopConfig.value);
  const edge = next.controller_inputs.find((item) => item.id === id);
  if (!edge) return;
  edge.mapping = mapping;
  setLoopConfig(next);
}

function updateControllerOutputMapping(id, mapping) {
  const next = clone(loopConfig.value);
  const edge = next.controller_outputs.find((item) => item.id === id);
  if (!edge) return;
  edge.mapping = mapping;
  setLoopConfig(next);
}

function removeControllerInput(id) {
  const next = clone(loopConfig.value);
  next.controller_inputs = next.controller_inputs.filter((item) => item.id !== id);
  setLoopConfig(next);
  if (selectedEdgeId.value === `controller_in:${id}`) selectedEdgeId.value = '';
}

function removeControllerOutput(id) {
  const next = clone(loopConfig.value);
  next.controller_outputs = next.controller_outputs.filter((item) => item.id !== id);
  setLoopConfig(next);
  if (selectedEdgeId.value === `controller_out:${id}`) selectedEdgeId.value = '';
}

function focusControllerEdge(edgeId, type) {
  selectedNodeId.value = '';
  selectedEdgeId.value = `${type}:${edgeId}`;
}

function createCapabilityItem() {
  return { name: '', binding: '', description: '' };
}

function onLoopKeyDown(event) {
  const target = event.target;
  const tagName = target?.tagName?.toLowerCase?.() || '';
  const isEditable =
    tagName === 'input' ||
    tagName === 'textarea' ||
    Boolean(target?.isContentEditable);
  if (isEditable) return;

  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    if (nestedLoopId.value) {
      nestedLoopId.value = '';
      return;
    }
    if (selectedEdgeId.value || selectedNodeId.value) {
      selectedEdgeId.value = '';
      selectedNodeId.value = '';
      return;
    }
    emit('close');
    return;
  }

  if ((event.metaKey || event.ctrlKey) && event.key === '1') {
    event.preventDefault();
    event.stopPropagation();
    addInnerNode('agent');
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === '2') {
    event.preventDefault();
    event.stopPropagation();
    addInnerNode('custom');
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === '3') {
    event.preventDefault();
    event.stopPropagation();
    addInnerNode('loop');
    return;
  }

  if (event.key !== 'Delete' && event.key !== 'Backspace') return;

  if (selectedEdgeId.value) {
    event.preventDefault();
    event.stopPropagation();
    deleteEdge(selectedEdgeId.value);
    return;
  }

  if (selectedNodeId.value && selectedNodeId.value !== CONTROLLER_IN_ID && selectedNodeId.value !== CONTROLLER_OUT_ID) {
    event.preventDefault();
    event.stopPropagation();
    deleteInnerNode(selectedNodeId.value);
  }
}

onMounted(() => {
  window.addEventListener('keydown', onLoopKeyDown, true);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onLoopKeyDown, true);
});
</script>

<template>
  <div class="loop-modal-backdrop" @click.self="$emit('close')">
    <div class="loop-modal-shell">
      <header class="loop-modal-header">
        <div>
          <div class="eyebrow">Loop Editor</div>
          <h2>{{ loopNode.label }}</h2>
          <p>Design the internal MASFactory loop graph. Controller In maps outer loop inputs into the subgraph. Controller Out maps inner node outputs back to the loop controller.</p>
        </div>
        <button type="button" class="ghost" @click="$emit('close')">Close</button>
      </header>

      <div class="loop-modal-grid">
        <aside class="loop-modal-sidebar">
          <section class="tool-group">
            <div class="group-title">Loop Settings</div>
            <label>
              <span>Loop Label</span>
              <input :value="loopNode.label" @input="$emit('rename-loop', { id: loopNode.id, label: $event.target.value })" />
            </label>
            <label>
              <span>Max Iterations</span>
              <input type="number" min="1" :value="loopConfig.max_iterations || 3" @input="updateLoopField('max_iterations', Number($event.target.value) || 1)" />
            </label>
            <label>
              <span>Controller Termination</span>
              <select :value="loopConfig.controller?.termination_mode || 'key_rule'" @change="updateControllerField('termination_mode', $event.target.value)">
                <option value="key_rule">Key Rule</option>
                <option value="prompt">Prompt Judge</option>
                <option value="expression">Expression</option>
              </select>
            </label>
            <div class="field-help">
              `Key Rule` is the current simplified UI. `Prompt Judge` maps to MASFactory <code>terminate_condition_prompt</code>. `Expression` is a safe serialized replacement for a custom <code>terminate_condition_function</code>.
            </div>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'prompt'">
              <span>Terminate Condition Prompt</span>
              <textarea
                :value="loopConfig.controller?.terminate_condition_prompt || ''"
                @input="updateControllerField('terminate_condition_prompt', $event.target.value)"
              />
            </label>
            <div v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'prompt'" class="field-help">
              Recommended format: describe the exact condition that means the loop should stop. Example: "Terminate only when the answer is complete, concrete, and includes implementation next steps."
            </div>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'prompt'">
              <span>Controller Model Name</span>
              <input
                :value="loopConfig.controller?.model_settings?.model_name || ''"
                placeholder="Optional override, otherwise use runtime model"
                @input="updateControllerModelField('model_name', $event.target.value)"
              />
            </label>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'prompt'">
              <span>Controller Base URL</span>
              <input
                :value="loopConfig.controller?.model_settings?.base_url || ''"
                placeholder="Optional OpenAI-compatible endpoint"
                @input="updateControllerModelField('base_url', $event.target.value)"
              />
            </label>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'expression'">
              <span>Terminate Expression</span>
              <textarea
                :value="loopConfig.controller?.terminate_expression || ''"
                @input="updateControllerField('terminate_expression', $event.target.value)"
              />
            </label>
            <div v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'expression'" class="field-help">
              Use a safe boolean expression over current loop-visible keys. Examples: <code>done == True</code>, <code>current_iteration &gt;= 3</code>, <code>answer and score &gt;= 0.9</code>, <code>input["done"] == True</code>.
            </div>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'key_rule'">
              <span>Terminate Mode</span>
              <select :value="loopConfig.terminate_when?.mode || 'never'" @change="updateTerminateField('mode', $event.target.value)">
                <option value="never">Never Stop Early</option>
                <option value="key_truthy">Stop When Key Is Truthy</option>
                <option value="key_equals">Stop When Key Equals Value</option>
              </select>
            </label>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'key_rule' && (loopConfig.terminate_when?.mode || 'never') !== 'never'">
              <span>Terminate Key</span>
              <input :value="loopConfig.terminate_when?.key || ''" @input="updateTerminateField('key', $event.target.value)" />
            </label>
            <label v-if="(loopConfig.controller?.termination_mode || 'key_rule') === 'key_rule' && loopConfig.terminate_when?.mode === 'key_equals'">
              <span>Terminate Value</span>
              <input :value="loopConfig.terminate_when?.value ?? true" @input="updateTerminateField('value', $event.target.value)" />
            </label>
            <div class="field-help">
              Shortcuts: <code>Ctrl/Cmd+1</code> add agent, <code>Ctrl/Cmd+2</code> add custom, <code>Ctrl/Cmd+3</code> add nested loop, <code>Delete</code> remove selected edge/node, <code>Esc</code> clear selection or close editor.
            </div>
          </section>

          <section class="tool-group">
            <div class="group-title">Controller Capabilities</div>
            <div class="field-help">
              MASFactory loop controllers can carry tools, memories, and retrievers into the controller runtime. ClawCanvas now binds supported declarations onto the real loop controller: tools support <code>builtin</code> and configured <code>api</code>, memories support <code>history_memory</code> and <code>vector_memory</code>, retrievers support <code>keyword_retriever</code>, <code>vector_retriever</code>, and <code>filesystem_retriever</code>. <code>mcp</code> still needs an external connector layer.
            </div>
            <div class="subsection-title">Controller Tools</div>
            <ObjectListEditor
              :value="loopConfig.controller?.tools || []"
              :fields="controllerCapabilityFields"
              :create-item="createCapabilityItem"
              @update:value="updateControllerField('tools', $event)"
            />
            <div class="subsection-title">Controller Memories</div>
            <ObjectListEditor
              :value="loopConfig.controller?.memories || []"
              :fields="controllerCapabilityFields"
              :create-item="createCapabilityItem"
              @update:value="updateControllerField('memories', $event)"
            />
            <div class="subsection-title">Controller Retrievers</div>
            <ObjectListEditor
              :value="loopConfig.controller?.retrievers || []"
              :fields="controllerCapabilityFields"
              :create-item="createCapabilityItem"
              @update:value="updateControllerField('retrievers', $event)"
            />
          </section>

          <section v-if="loopWarnings.length" class="tool-group">
            <div class="group-title">Loop Warnings</div>
            <div v-for="warning in loopWarnings" :key="warning" class="field-help warning-text">
              {{ warning }}
            </div>
          </section>

          <section v-if="internalOnlyKeys.length" class="tool-group">
            <div class="group-title">Internal Keys</div>
            <div class="field-help">
              These keys exist inside the loop subgraph but are not exported through controller outputs yet, so they are not guaranteed to be visible to outer workflow nodes:
              <code>{{ internalOnlyKeys.join(', ') }}</code>
            </div>
          </section>

          <section class="tool-group">
            <div class="group-title">Inner Nodes</div>
            <button type="button" @click="addInnerNode('agent')">Add Agent</button>
            <button type="button" @click="addInnerNode('custom')">Add Custom</button>
            <button type="button" @click="addInnerNode('loop')">Add Loop</button>
            <div class="field-help">
              Connect <code>Controller In</code> to the first inner nodes that should receive each iteration input, and connect terminating inner nodes to <code>Controller Out</code>.
            </div>
          </section>

          <section class="tool-group">
            <div class="group-title">Controller Inputs</div>
            <div class="field-help">
              These edges correspond to MASFactory <code>edge_from_controller</code>. They inject outer loop context into selected inner nodes.
            </div>
            <div v-if="!loopConfig.controller_inputs.length" class="field-help">No controller inputs yet.</div>
            <div v-for="item in loopConfig.controller_inputs" :key="item.id" class="object-card">
              <div class="row-head">{{ item.id }}</div>
              <label>
                <span>Target Node</span>
                <select :value="item.target" @change="updateControllerInputTarget(item.id, $event.target.value)">
                  <option v-for="node in innerNodeOptions" :key="node.id" :value="node.id">{{ node.label }}</option>
                </select>
              </label>
              <MapEditor
                :value="item.mapping || {}"
                key-label="Loop Key"
                value-label="Meaning"
                :suggestions="mergeSuggestions(mappingSuggestions(keyPool.key_map || {}), mappingSuggestions((loopConfig.subgraph.nodes || []).find((node) => node.id === item.target)?.config?.pull_keys || {}))"
                suggestion-title="Workflow Key Pool"
                @update:value="updateControllerInputMapping(item.id, $event)"
              />
              <div class="controller-actions">
                <button type="button" class="ghost mini-button" @click="focusControllerEdge(item.id, 'controller_in')">Focus Edge</button>
                <button type="button" class="danger-button mini-button" @click="removeControllerInput(item.id)">Remove</button>
              </div>
            </div>
            <button type="button" class="mini-button" @click="addControllerInput">Add Controller Input</button>
          </section>

          <section class="tool-group">
            <div class="group-title">Controller Outputs</div>
            <div class="field-help">
              These edges correspond to MASFactory <code>edge_to_controller</code>. They send inner node results back to the loop controller and outer workflow.
            </div>
            <div v-if="!loopConfig.controller_outputs.length" class="field-help">No controller outputs yet.</div>
            <div v-for="item in loopConfig.controller_outputs" :key="item.id" class="object-card">
              <div class="row-head">{{ item.id }}</div>
              <label>
                <span>Source Node</span>
                <select :value="item.source" @change="updateControllerOutputSource(item.id, $event.target.value)">
                  <option v-for="node in innerNodeOptions" :key="node.id" :value="node.id">{{ node.label }}</option>
                </select>
              </label>
              <MapEditor
                :value="item.mapping || {}"
                key-label="Loop Key"
                value-label="Meaning"
                :suggestions="mergeSuggestions(mappingSuggestions((loopConfig.subgraph.nodes || []).find((node) => node.id === item.source)?.config?.push_keys || {}), mappingSuggestions(keyPool.key_map || {}))"
                suggestion-title="Workflow Key Pool"
                @update:value="updateControllerOutputMapping(item.id, $event)"
              />
              <div class="controller-actions">
                <button type="button" class="ghost mini-button" @click="focusControllerEdge(item.id, 'controller_out')">Focus Edge</button>
                <button type="button" class="danger-button mini-button" @click="removeControllerOutput(item.id)">Remove</button>
              </div>
            </div>
            <button type="button" class="mini-button" @click="addControllerOutput">Add Controller Output</button>
          </section>

          <section v-if="selectedEdge" class="tool-group">
            <div class="group-title">Selected Edge</div>
            <div class="field-help">{{ controllerDisplay(selectedEdge) }}</div>
            <MapEditor
              :value="selectedEdge.mapping"
              key-label="Key"
              value-label="Meaning"
              :suggestions="mappingSuggestionsForSelectedEdge()"
              suggestion-title="Suggested Keys"
              @update:value="updateEdgeMapping(selectedEdge.id, $event)"
            />
            <button type="button" class="danger-button" @click="deleteEdge(selectedEdge.id)">Delete Edge</button>
          </section>

          <LoopNodeInspector
            :selected-node="selectedNode"
            :document="innerDocument"
            :key-pool="keyPool"
            @update-node="updateInnerNode"
            @delete-node="deleteInnerNode"
            @open-loop="openNestedLoop"
          />
        </aside>

        <main class="loop-modal-main">
          <CanvasBoard
            :nodes="canvasNodes"
            :edges="innerDocument.edges"
            :selected-node-id="selectedNodeId"
            :selected-edge-id="selectedEdgeId"
            @select-node="selectNode"
            @select-edge="selectEdge"
            @move-node="moveInnerNode"
            @create-edge="createEdge"
            @rename-node="renameInnerNode"
            @open-loop="openNestedLoop"
          />
        </main>
      </div>

      <LoopEditorModal
        v-if="nestedLoopNode"
        :loop-node="nestedLoopNode"
        :key-pool="keyPool"
        @close="nestedLoopId = ''"
        @rename-loop="renameInnerNode"
        @update-loop-config="updateNestedLoopConfig"
      />
    </div>
  </div>
</template>
