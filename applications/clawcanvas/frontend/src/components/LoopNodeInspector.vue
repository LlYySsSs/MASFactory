<script setup>
import { computed } from 'vue';
import MapEditor from './MapEditor.vue';
import ObjectListEditor from './ObjectListEditor.vue';
import StringListEditor from './StringListEditor.vue';

const props = defineProps({
  selectedNode: { type: Object, default: null },
  document: { type: Object, required: true },
  keyPool: { type: Object, required: true }
});

const emit = defineEmits(['update-node', 'delete-node', 'open-loop']);

const toolFields = [
  { key: 'name', label: 'Name', placeholder: 'echo / json_inspect / http_api' },
  {
    key: 'binding',
    label: 'Binding',
    options: [
      { value: 'mcp', label: 'mcp' },
      { value: 'builtin', label: 'builtin' },
      { value: 'api', label: 'api' },
      { value: 'other', label: 'other' }
    ]
  },
  { key: 'description', label: 'Description', placeholder: 'What this tool does', multiline: true }
];

const knowledgeFields = [
  { key: 'title', label: 'Title', placeholder: 'Refund policy' },
  { key: 'text', label: 'Text', placeholder: 'Knowledge content or summary', multiline: true }
];

const nodeBehaviorRuleSuggestions = [
  'Keep the answer concise.',
  'Only use the provided context.',
  'List assumptions briefly.',
  'Return structured output.'
];
const toolPresets = [
  { label: 'Echo', description: 'Return text unchanged', item: { name: 'echo', binding: 'builtin', description: 'Echo input text for quick debugging or prompt chaining.' } },
  { label: 'JSON Inspect', description: 'Pretty-print payload as JSON', item: { name: 'json_inspect', binding: 'builtin', description: 'Render payload as formatted JSON for inspection.' } },
  { label: 'List Keys', description: 'List top-level keys', item: { name: 'list_keys', binding: 'builtin', description: 'Return the top-level keys of a dict-like payload.' } },
  { label: 'HTTP API', description: 'Call external API', item: { name: 'http_api', binding: 'api', description: 'method=POST; url=https://example.com/endpoint; body={\"query\":\"{query}\"}; response=json' } }
];
const knowledgePresets = [
  { label: 'Policy', description: 'Business policy', item: { title: 'Policy', text: 'Describe the rule.' } },
  { label: 'Reference', description: 'Reference note', item: { title: 'Reference', text: 'Add a factual note.' } }
];
const customModeOptions = [
  { value: 'passthrough', label: 'Passthrough' },
  { value: 'template', label: 'Template' },
  { value: 'set', label: 'Set Static Values' },
  { value: 'pick', label: 'Pick Inputs' }
];

function createToolItem() {
  return { name: '', binding: '', description: '' };
}

function createKnowledgeItem() {
  return { title: '', text: '' };
}

function updateNodeField(field, value) {
  if (!props.selectedNode) return;
  emit('update-node', { id: props.selectedNode.id, patch: { [field]: value } });
}

function updateNodeConfig(field, value) {
  if (!props.selectedNode) return;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: { config: { ...props.selectedNode.config, [field]: value } }
  });
}

function mergeSuggestions(...groups) {
  const map = new Map();
  for (const group of groups) {
    for (const item of group || []) {
      const key = String(item?.key || '').trim();
      if (!key) continue;
      if (!map.has(key)) {
        map.set(key, { key, value: String(item?.value || '') });
      }
    }
  }
  return [...map.values()];
}

function mappingSuggestions(mapping) {
  return Object.entries(mapping || {}).map(([key, value]) => ({
    key: String(key),
    value: String(value ?? '')
  }));
}

function incomingEdges(nodeId) {
  return (props.document?.edges || []).filter((edge) => edge.target === nodeId);
}

function outgoingEdges(nodeId) {
  return (props.document?.edges || []).filter((edge) => edge.source === nodeId);
}

const globalKeySuggestions = computed(() => mappingSuggestions(props.keyPool?.key_map || {}));
const selectedIncomingSuggestions = computed(() => {
  if (!props.selectedNode) return [];
  return mergeSuggestions(...incomingEdges(props.selectedNode.id).map((edge) => mappingSuggestions(edge.mapping)));
});
const selectedOutgoingSuggestions = computed(() => {
  if (!props.selectedNode) return [];
  return mergeSuggestions(...outgoingEdges(props.selectedNode.id).map((edge) => mappingSuggestions(edge.mapping)));
});
const incomingKeyNames = computed(() => selectedIncomingSuggestions.value.map((item) => item.key));
const outgoingKeyNames = computed(() => selectedOutgoingSuggestions.value.map((item) => item.key));

const agentPullSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Input message' },
    { key: 'context', value: 'Context' }
  ])
);
const agentPushSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedOutgoingSuggestions.value, [
    { key: 'answer', value: 'Main answer' },
    { key: 'summary', value: 'Summary' }
  ])
);
const customPullSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Input message' },
    { key: 'context', value: 'Context' }
  ])
);
const customPushSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedOutgoingSuggestions.value, [
    { key: 'message', value: 'Output message' },
    { key: 'result', value: 'Result' }
  ])
);

function extractPlaceholders(text) {
  const matches = String(text || '').match(/\{([^{}]+)\}/g) || [];
  return [...new Set(matches.map((item) => item.slice(1, -1).trim()).filter(Boolean))];
}

const promptWarnings = computed(() => {
  if (props.selectedNode?.type !== 'agent') return [];
  const allowed = new Set(Object.keys(props.selectedNode.config?.pull_keys || {}));
  const global = new Set(props.keyPool?.key_names || []);
  return extractPlaceholders(props.selectedNode.config?.prompt_template || '').map((key) => {
    if (allowed.has(key)) return null;
    if (global.has(key)) return `Prompt template: {${key}} is in workflow key pool but missing from pull_keys.`;
    return `Prompt template: {${key}} cannot be found in pull_keys or workflow key pool.`;
  }).filter(Boolean);
});
</script>

<template>
  <section class="panel-section loop-panel-scroll">
    <div class="section-title">Selected Inner Node</div>
    <template v-if="selectedNode">
      <label>
        <span>Label</span>
        <input :value="selectedNode.label" @input="updateNodeField('label', $event.target.value)" />
      </label>
      <label>
        <span>Type</span>
        <input :value="selectedNode.type" disabled />
      </label>

      <template v-if="selectedNode.type === 'agent'">
        <label>
          <span>Instructions</span>
          <textarea :value="selectedNode.config.instructions || ''" @input="updateNodeConfig('instructions', $event.target.value)" />
        </label>
        <label>
          <span>Prompt Template</span>
          <textarea :value="selectedNode.config.prompt_template || ''" @input="updateNodeConfig('prompt_template', $event.target.value)" />
        </label>
        <div v-if="promptWarnings.length" class="warning-block">
          <div class="warning-title">Prompt Warnings</div>
          <div v-for="warning in promptWarnings" :key="warning" class="field-help warning-text">{{ warning }}</div>
        </div>

        <div class="subsection-title">Pull Keys</div>
        <MapEditor
          :value="selectedNode.config.pull_keys || {}"
          key-label="Input Key"
          value-label="Meaning"
          :suggestions="agentPullSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('pull_keys', $event)"
        />
        <div v-if="incomingKeyNames.length" class="field-help">Upstream reachable keys: <code>{{ incomingKeyNames.join(', ') }}</code></div>

        <div class="subsection-title">Push Keys</div>
        <MapEditor
          :value="selectedNode.config.push_keys || {}"
          key-label="Output Key"
          value-label="Meaning"
          :suggestions="agentPushSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('push_keys', $event)"
        />
        <div v-if="outgoingKeyNames.length" class="field-help">Downstream edges reference: <code>{{ outgoingKeyNames.join(', ') }}</code></div>

        <div class="subsection-title">Behavior Rules</div>
        <StringListEditor
          :value="selectedNode.config.behavior_rules || []"
          placeholder="Keep the answer concise."
          :suggestions="nodeBehaviorRuleSuggestions"
          suggestion-title="Common Node Rules"
          @update:value="updateNodeConfig('behavior_rules', $event)"
        />

        <div class="subsection-title">Knowledge</div>
        <ObjectListEditor
          :value="selectedNode.config.knowledge || []"
          :fields="knowledgeFields"
          :create-item="createKnowledgeItem"
          :presets="knowledgePresets"
          preset-title="Quick Add Knowledge"
          @update:value="updateNodeConfig('knowledge', $event)"
        />

        <div class="subsection-title">Tools</div>
        <ObjectListEditor
          :value="selectedNode.config.tools || []"
          :fields="toolFields"
          :create-item="createToolItem"
          :presets="toolPresets"
          preset-title="Quick Add Tools"
          @update:value="updateNodeConfig('tools', $event)"
        />
      </template>

      <template v-else-if="selectedNode.type === 'custom'">
        <label>
          <span>Mode</span>
          <select :value="selectedNode.config.mode || 'passthrough'" @change="updateNodeConfig('mode', $event.target.value)">
            <option v-for="option in customModeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
        </label>

        <div v-if="(selectedNode.config.mode || 'passthrough') === 'template'" class="subsection-title">Templates</div>
        <MapEditor
          v-if="(selectedNode.config.mode || 'passthrough') === 'template'"
          :value="selectedNode.config.templates || {}"
          key-label="Output Key"
          value-label="Template"
          :suggestions="customPushSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('templates', $event)"
        />

        <div v-if="selectedNode.config.mode === 'set'" class="subsection-title">Static Outputs</div>
        <MapEditor
          v-if="selectedNode.config.mode === 'set'"
          :value="selectedNode.config.static_outputs || {}"
          key-label="Output Key"
          value-label="Static Value"
          :suggestions="customPushSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('static_outputs', $event)"
        />

        <div v-if="selectedNode.config.mode === 'pick'" class="subsection-title">Pick Keys</div>
        <MapEditor
          v-if="selectedNode.config.mode === 'pick'"
          :value="selectedNode.config.pick_keys || {}"
          key-label="Output Key"
          value-label="Source Key"
          :suggestions="customPullSuggestions"
          suggestion-title="Workflow Key Pool"
          suggestion-value-mode="key"
          @update:value="updateNodeConfig('pick_keys', $event)"
        />

        <div class="subsection-title">Pull Keys</div>
        <MapEditor
          :value="selectedNode.config.pull_keys || {}"
          key-label="Input Key"
          value-label="Meaning"
          :suggestions="customPullSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('pull_keys', $event)"
        />
        <div v-if="incomingKeyNames.length" class="field-help">Upstream reachable keys: <code>{{ incomingKeyNames.join(', ') }}</code></div>

        <div class="subsection-title">Push Keys</div>
        <MapEditor
          :value="selectedNode.config.push_keys || {}"
          key-label="Output Key"
          value-label="Meaning"
          :suggestions="customPushSuggestions"
          suggestion-title="Workflow Key Pool"
          @update:value="updateNodeConfig('push_keys', $event)"
        />
        <div v-if="outgoingKeyNames.length" class="field-help">Downstream edges reference: <code>{{ outgoingKeyNames.join(', ') }}</code></div>
      </template>

      <template v-else-if="selectedNode.type === 'loop'">
        <div class="field-help">
          This is a nested loop node. Open its own editor to design inner nodes, controller input mappings, and controller output mappings.
        </div>
        <button type="button" @click="$emit('open-loop', selectedNode.id)">Edit Nested Loop</button>
      </template>

      <button type="button" class="danger-button" @click="$emit('delete-node', selectedNode.id)">Delete Node</button>
    </template>
    <p v-else class="empty-state">Select an inner node to edit it.</p>
  </section>
</template>
