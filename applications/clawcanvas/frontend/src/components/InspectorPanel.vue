<script setup>
import { computed, ref, watch } from 'vue';
import BehaviorEditor from './BehaviorEditor.vue';
import MapEditor from './MapEditor.vue';
import ObjectListEditor from './ObjectListEditor.vue';
import StringListEditor from './StringListEditor.vue';

const props = defineProps({
  selectedNode: { type: Object, default: null },
  manifest: { type: Object, required: true },
  document: { type: Object, required: true },
  keyPool: { type: Object, required: true }
});

const emit = defineEmits(['update-node', 'update-manifest', 'delete-node', 'open-loop-editor', 'open-custom-editor']);

const detailGroup = ref('');
const detailSection = ref('');
const nodeModalGroups = new Set(['node', 'agent', 'custom', 'loop']);

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
    ],
    help: 'Binding means how this tool is connected at runtime. builtin and api are wired by the current backend. mcp still needs an external endpoint/config layer before it can run.'
  },
  { key: 'description', label: 'Description', placeholder: 'What this tool does', multiline: true }
];

const knowledgeFields = [
  { key: 'title', label: 'Title', placeholder: 'Refund policy' },
  { key: 'text', label: 'Text', placeholder: 'Knowledge content or summary', multiline: true }
];

const tagSuggestions = ['faq', 'customer-service', 'workflow', 'research', 'analysis', 'automation'];
const behaviorStyleSuggestions = ['structured', 'concise', 'formal', 'coach-like', 'step-by-step'];
const behaviorRuleSuggestions = [
  'Explain the basis of the answer.',
  'Do not invent missing facts.',
  'Keep the output actionable.',
  'Separate assumptions from conclusions.'
];
const nodeBehaviorRuleSuggestions = [
  'Keep the answer concise.',
  'Only use the provided context.',
  'List assumptions briefly.',
  'Return structured output.'
];
const toolPresets = [
  {
    label: 'Echo',
    description: 'Return text unchanged',
    item: { name: 'echo', binding: 'builtin', description: 'Echo input text for quick debugging or prompt chaining.' }
  },
  {
    label: 'JSON Inspect',
    description: 'Pretty-print payload as JSON',
    item: { name: 'json_inspect', binding: 'builtin', description: 'Render payload as formatted JSON for inspection.' }
  },
  {
    label: 'List Keys',
    description: 'List top-level keys from an object payload',
    item: { name: 'list_keys', binding: 'builtin', description: 'Return the top-level keys of a dict-like payload.' }
  },
  {
    label: 'HTTP API',
    description: 'Call an external API service',
    item: {
      name: 'http_api',
      binding: 'api',
      description: 'method=POST; url=https://example.com/endpoint; body={\"query\":\"{query}\"}; response=json'
    }
  }
];
const knowledgePresets = [
  {
    label: 'Policy',
    description: 'Business rule or platform policy',
    item: { title: 'Policy', text: 'Describe the business rule or policy this skill must follow.' }
  },
  {
    label: 'Terminology',
    description: 'Important domain terms',
    item: { title: 'Terminology', text: 'Define the domain-specific terms used in this workflow.' }
  },
  {
    label: 'Reference',
    description: 'Reference summary or factual note',
    item: { title: 'Reference Note', text: 'Add a concise factual summary the node should rely on.' }
  }
];
const terminateModeOptions = [
  { value: 'never', label: 'Never Stop Early' },
  { value: 'key_truthy', label: 'Stop When Key Is Truthy' },
  { value: 'key_equals', label: 'Stop When Key Equals Value' }
];
const keyRuleHelp =
  'Key names are identifiers like query, analysis_result, answer, done. Use lowercase letters, numbers, and underscores when possible. Nodes may define new keys; edges map one node output key to another node input key.';

const manifestNav = [
  { id: 'overview', label: 'Overview', help: 'Name, version, description' },
  { id: 'tags', label: 'Tags', help: 'Search and categorization labels' },
  { id: 'tools', label: 'Tools', help: 'Shared runtime tools' },
  { id: 'knowledge', label: 'Knowledge', help: 'Shared domain context' },
  { id: 'behavior', label: 'Behavior', help: 'Shared behavior rules' }
];

const agentNav = [
  { id: 'basics', label: 'Basics', help: 'Node identity and quick actions' },
  { id: 'prompt', label: 'Prompt', help: 'Instructions and prompt template' },
  { id: 'keys', label: 'Keys', help: 'Pull keys and push keys' },
  { id: 'capabilities', label: 'Capabilities', help: 'Tools, knowledge, behavior rules' }
];

const customNav = [
  { id: 'basics', label: 'Basics', help: 'Node identity and editor entry' },
  { id: 'runtime', label: 'Runtime View', help: 'Mode and key summary' }
];

const loopNav = [
  { id: 'basics', label: 'Basics', help: 'Node identity and quick actions' },
  { id: 'termination', label: 'Termination', help: 'Max iterations and stop rules' },
  { id: 'structure', label: 'Structure', help: 'Loop editor entry and graph summary' }
];

const genericNodeNav = [{ id: 'basics', label: 'Basics', help: 'Node identity and quick actions' }];

watch(
  () => props.selectedNode?.id || '',
  () => {
    if (nodeModalGroups.has(detailGroup.value)) {
      closeDetail();
    }
  }
);

function defaultSectionForGroup(group) {
  if (group === 'manifest') return 'overview';
  if (group === 'agent') return 'basics';
  if (group === 'custom') return 'basics';
  if (group === 'loop') return 'basics';
  if (group === 'node') return 'basics';
  return '';
}

function openDetail(group, section = '') {
  detailGroup.value = group;
  detailSection.value = section || defaultSectionForGroup(group);
}

function closeDetail() {
  detailGroup.value = '';
  detailSection.value = '';
}

function selectSection(sectionId) {
  detailSection.value = sectionId;
}

function createToolItem() {
  return { name: '', binding: '', description: '' };
}

function createKnowledgeItem() {
  return { title: '', text: '' };
}

function updateNodeField(field, value) {
  if (!props.selectedNode) return;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: { [field]: value }
  });
}

function updateNodeConfig(field, value) {
  if (!props.selectedNode) return;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: {
      config: {
        ...props.selectedNode.config,
        [field]: value
      }
    }
  });
}

function updateNestedConfig(rootField, field, value) {
  if (!props.selectedNode) return;
  const root = props.selectedNode.config[rootField] || {};
  emit('update-node', {
    id: props.selectedNode.id,
    patch: {
      config: {
        ...props.selectedNode.config,
        [rootField]: {
          ...root,
          [field]: value
        }
      }
    }
  });
}

function updateManifest(field, value) {
  emit('update-manifest', { [field]: value });
}

function mergeSuggestions(...groups) {
  const map = new Map();
  for (const group of groups) {
    for (const item of group || []) {
      const key = String(item?.key || '').trim();
      if (!key) continue;
      if (!map.has(key)) {
        map.set(key, { key, value: String(item?.value || '').trim() });
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

const globalKeySuggestions = computed(() => mappingSuggestions(props.keyPool?.key_map || {}));

function incomingEdges(nodeId) {
  return (props.document?.edges || []).filter((edge) => edge.target === nodeId);
}

function outgoingEdges(nodeId) {
  return (props.document?.edges || []).filter((edge) => edge.source === nodeId);
}

const selectedIncomingSuggestions = computed(() => {
  if (!props.selectedNode) return [];
  return mergeSuggestions(...incomingEdges(props.selectedNode.id).map((edge) => mappingSuggestions(edge.mapping)));
});

const selectedOutgoingSuggestions = computed(() => {
  if (!props.selectedNode) return [];
  return mergeSuggestions(...outgoingEdges(props.selectedNode.id).map((edge) => mappingSuggestions(edge.mapping)));
});

const agentPullSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedIncomingSuggestions.value, [
    { key: 'query', value: 'Original user request' },
    { key: 'message', value: 'Input message' },
    { key: 'context', value: 'Relevant context' }
  ])
);

const agentPushSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedOutgoingSuggestions.value, [
    { key: 'answer', value: 'Main answer' },
    { key: 'analysis', value: 'Structured analysis' },
    { key: 'summary', value: 'Short summary' }
  ])
);

const incomingKeyNames = computed(() => selectedIncomingSuggestions.value.map((item) => item.key));
const outgoingKeyNames = computed(() => selectedOutgoingSuggestions.value.map((item) => item.key));

function extractPlaceholders(text) {
  const matches = String(text || '').match(/\{([^{}]+)\}/g) || [];
  return [...new Set(matches.map((item) => item.slice(1, -1).trim()).filter(Boolean))];
}

function promptWarnings(promptTemplate, allowedKeys, globalKeys, scopeLabel) {
  const allowed = new Set(Object.keys(allowedKeys || {}));
  const global = new Set((globalKeys || []).map((item) => String(item)));
  return extractPlaceholders(promptTemplate)
    .map((key) => {
      if (allowed.has(key)) return null;
      if (global.has(key)) {
        return `${scopeLabel}: {${key}} is in workflow key pool but missing from pull_keys.`;
      }
      return `${scopeLabel}: {${key}} cannot be found in pull_keys or workflow key pool.`;
    })
    .filter(Boolean);
}

const agentPromptWarnings = computed(() =>
  promptWarnings(
    props.selectedNode?.config?.prompt_template || '',
    props.selectedNode?.config?.pull_keys || {},
    props.keyPool?.key_names || [],
    'Prompt template'
  )
);

const manifestSummary = computed(() => [
  { label: 'Tags', value: String((props.manifest.tags || []).length) },
  { label: 'Tools', value: String((props.manifest.tools || []).length) },
  { label: 'Knowledge', value: String((props.manifest.knowledge || []).length) },
  { label: 'Rules', value: String((props.manifest.behavior?.rules || []).length) }
]);

const selectedNodeSummary = computed(() => {
  const node = props.selectedNode;
  if (!node) return [];
  if (node.type === 'agent') {
    return [
      { label: 'Pull Keys', value: String(Object.keys(node.config.pull_keys || {}).length) },
      { label: 'Push Keys', value: String(Object.keys(node.config.push_keys || {}).length) },
      { label: 'Tools', value: String((node.config.tools || []).length) },
      { label: 'Knowledge', value: String((node.config.knowledge || []).length) }
    ];
  }
  if (node.type === 'custom') {
    return [
      { label: 'Mode', value: String(node.config.mode || 'python') },
      { label: 'Pull Keys', value: String(Object.keys(node.config.pull_keys || {}).length) },
      { label: 'Push Keys', value: String(Object.keys(node.config.push_keys || {}).length) }
    ];
  }
  if (node.type === 'loop') {
    return [
      { label: 'Inner Nodes', value: String((node.config.subgraph?.nodes || []).length) },
      { label: 'Inner Edges', value: String((node.config.subgraph?.edges || []).length) },
      { label: 'Controller In', value: String((node.config.controller_inputs || []).length) },
      { label: 'Controller Out', value: String((node.config.controller_outputs || []).length) }
    ];
  }
  return [{ label: 'Node Type', value: node.type }];
});

const modalOpen = computed(() => Boolean(detailGroup.value));
const selectedNodeTypeLabel = computed(() => {
  if (!props.selectedNode) return '';
  return `${props.selectedNode.type} node`;
});

const canDeleteSelectedNode = computed(() =>
  Boolean(props.selectedNode && props.selectedNode.type !== 'start' && props.selectedNode.type !== 'end')
);

const currentNavSections = computed(() => {
  if (detailGroup.value === 'manifest') return manifestNav;
  if (detailGroup.value === 'agent') return agentNav;
  if (detailGroup.value === 'custom') return customNav;
  if (detailGroup.value === 'loop') return loopNav;
  if (detailGroup.value === 'node') return genericNodeNav;
  return [];
});

const modalTitle = computed(() => {
  if (detailGroup.value === 'manifest') return 'Skill Manifest Editor';
  if (!props.selectedNode) return 'Inspector';
  if (detailGroup.value === 'agent') return `${props.selectedNode.label} · Agent Editor`;
  if (detailGroup.value === 'custom') return `${props.selectedNode.label} · Custom Node`;
  if (detailGroup.value === 'loop') return `${props.selectedNode.label} · Loop Settings`;
  if (detailGroup.value === 'node') return `${props.selectedNode.label} · Node Basics`;
  return 'Inspector';
});

const modalDescription = computed(() => {
  if (detailGroup.value === 'manifest') {
    return 'Define the skill package here. Use the left navigation to move between overview, tags, tools, knowledge, and behavior.';
  }
  if (detailGroup.value === 'agent') {
    return 'Configure the selected agent here. Edit its prompt, workflow keys, and runtime capabilities section by section.';
  }
  if (detailGroup.value === 'custom') {
    return 'Review the selected custom node here, then open the custom editor to write or update its Python logic.';
  }
  if (detailGroup.value === 'loop') {
    return 'Edit loop settings here, then open the loop editor to build the inner subgraph and controller connections.';
  }
  if (detailGroup.value === 'node') {
    return 'Update the selected node label and review its basic configuration here.';
  }
  return '';
});
</script>

<template>
  <div class="inspector-panel">
    <section class="panel-section inspector-summary-card">
      <div class="section-title">Skill Manifest</div>
      <div class="helper-text">
        Review the current skill package at a glance, then open the editor to update metadata, shared tools, and shared guidance.
      </div>

      <div class="object-card">
        <div class="inspector-kv">
          <div class="inspector-kv-row">
            <span>Name</span>
            <strong>{{ manifest.name || 'untitled_skill' }}</strong>
          </div>
          <div class="inspector-kv-row">
            <span>Version</span>
            <strong>{{ manifest.version || '0.1.0' }}</strong>
          </div>
          <div class="inspector-kv-row">
            <span>Description</span>
            <strong>{{ manifest.description || 'No description yet' }}</strong>
          </div>
        </div>
      </div>

      <div class="summary-metrics">
        <div v-for="item in manifestSummary" :key="item.label" class="metric-chip">
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </div>
      </div>

      <button type="button" class="ghost" @click="openDetail('manifest', 'overview')">Open Skill Manifest</button>
    </section>

    <section class="panel-section inspector-summary-card">
      <div class="section-title">Selected Node</div>
      <template v-if="selectedNode">
        <div class="object-card inspector-node-card">
          <div>
            <div class="eyebrow">{{ selectedNodeTypeLabel }}</div>
            <h3 class="inspector-node-title">{{ selectedNode.label }}</h3>
            <div class="helper-text"><code>{{ selectedNode.id }}</code></div>
          </div>
          <div class="helper-text">
            Review the selected node here, then open the matching editor to change labels, prompts, keys, loop settings, or custom logic.
          </div>
        </div>

        <div class="summary-metrics">
          <div v-for="item in selectedNodeSummary" :key="item.label" class="metric-chip">
            <strong>{{ item.value }}</strong>
            <span>{{ item.label }}</span>
          </div>
        </div>

        <div class="inspector-action-list">
          <template v-if="selectedNode.type === 'agent'">
            <button type="button" class="ghost" @click="openDetail('agent', 'basics')">Open Agent Editor</button>
            <button type="button" class="ghost" @click="openDetail('agent', 'prompt')">Prompt</button>
            <button type="button" class="ghost" @click="openDetail('agent', 'keys')">Keys</button>
          </template>

          <template v-else-if="selectedNode.type === 'custom'">
            <button type="button" class="ghost" @click="openDetail('custom', 'basics')">Open Custom Overview</button>
            <button type="button" @click="$emit('open-custom-editor', selectedNode.id)">Edit Custom Node</button>
          </template>

          <template v-else-if="selectedNode.type === 'loop'">
            <button type="button" class="ghost" @click="openDetail('loop', 'basics')">Open Loop Overview</button>
            <button type="button" class="ghost" @click="openDetail('loop', 'termination')">Termination</button>
            <button type="button" @click="$emit('open-loop-editor', selectedNode.id)">Edit Loop</button>
          </template>

          <template v-else>
            <button type="button" class="ghost" @click="openDetail('node', 'basics')">Open Node Basics</button>
          </template>

          <button
            v-if="canDeleteSelectedNode"
            type="button"
            class="danger-button"
            @click="$emit('delete-node', selectedNode.id)"
          >
            Delete Node
          </button>
        </div>
      </template>

      <p v-else class="empty-state">
        Select a node on the canvas to see its summary, then open the corresponding full-size editor.
      </p>
    </section>

    <Teleport to="body">
      <div v-if="modalOpen" class="loop-modal-backdrop" @click.self="closeDetail">
        <div class="loop-modal-shell inspector-modal-shell">
          <header class="loop-modal-header">
            <div>
              <div class="eyebrow">Right Inspector</div>
              <h2>{{ modalTitle }}</h2>
              <p>{{ modalDescription }}</p>
            </div>
            <button type="button" class="ghost" @click="closeDetail">Close</button>
          </header>

          <div class="inspector-modal-grid">
            <aside class="loop-modal-sidebar inspector-modal-sidebar">
              <section class="tool-group">
                <div class="group-title">
                  {{ detailGroup === 'manifest' ? 'Manifest Sections' : 'Editor Sections' }}
                </div>
                <div class="inspector-nav-list">
                  <button
                    v-for="item in currentNavSections"
                    :key="item.id"
                    type="button"
                    class="ghost inspector-nav-button"
                    :class="{ active: detailSection === item.id }"
                    @click="selectSection(item.id)"
                  >
                    <span>{{ item.label }}</span>
                    <small>{{ item.help }}</small>
                  </button>
                </div>
              </section>

              <section class="tool-group">
                <div class="group-title">
                  {{ detailGroup === 'manifest' ? 'Manifest Summary' : 'Node Summary' }}
                </div>
                <div class="summary-metrics">
                  <div
                    v-for="item in detailGroup === 'manifest' ? manifestSummary : selectedNodeSummary"
                    :key="item.label"
                    class="metric-chip"
                  >
                    <strong>{{ item.value }}</strong>
                    <span>{{ item.label }}</span>
                  </div>
                </div>
                <div v-if="detailGroup !== 'manifest' && selectedNode" class="field-help">
                  Current node: <code>{{ selectedNode.id }}</code>
                </div>
              </section>

              <section class="tool-group">
                <div class="group-title">Quick Actions</div>
                <template v-if="detailGroup === 'manifest'">
                  <button type="button" class="ghost" @click="selectSection('tools')">Jump To Tools</button>
                  <button type="button" class="ghost" @click="selectSection('behavior')">Jump To Behavior</button>
                </template>
                <template v-else-if="detailGroup === 'agent' && selectedNode">
                  <button type="button" class="ghost" @click="selectSection('prompt')">Edit Prompt</button>
                  <button type="button" class="ghost" @click="selectSection('keys')">Edit Keys</button>
                </template>
                <template v-else-if="detailGroup === 'custom' && selectedNode">
                  <button type="button" @click="$emit('open-custom-editor', selectedNode.id)">Open Custom Editor</button>
                </template>
                <template v-else-if="detailGroup === 'loop' && selectedNode">
                  <button type="button" @click="$emit('open-loop-editor', selectedNode.id)">Open Loop Editor</button>
                </template>
                <button
                  v-if="detailGroup !== 'manifest' && canDeleteSelectedNode && selectedNode"
                  type="button"
                  class="danger-button"
                  @click="$emit('delete-node', selectedNode.id)"
                >
                  Delete Node
                </button>
              </section>
            </aside>

            <main class="inspector-modal-main">
              <section v-if="detailGroup === 'manifest' && detailSection === 'overview'" class="panel-section">
                <div class="section-title">Manifest Overview</div>
                <div class="helper-text">
                  Manifest describes the whole skill package. These values are exported with the workflow and should describe what the skill does overall, not just one node.
                </div>

                <label>
                  <span>Name</span>
                  <input :value="manifest.name" @input="updateManifest('name', $event.target.value)" />
                </label>
                <label>
                  <span>Version</span>
                  <input :value="manifest.version" @input="updateManifest('version', $event.target.value)" />
                </label>
                <label>
                  <span>Description</span>
                  <textarea :value="manifest.description" @input="updateManifest('description', $event.target.value)" />
                </label>
              </section>

              <section v-else-if="detailGroup === 'manifest' && detailSection === 'tags'" class="panel-section">
                <div class="section-title">Manifest Tags</div>
                <div class="helper-text">
                  Tags are short labels used for search and categorization in exported skill metadata.
                </div>
                <StringListEditor
                  :value="manifest.tags || []"
                  placeholder="faq / customer-service / workflow"
                  help="Use short searchable labels."
                  :suggestions="tagSuggestions"
                  suggestion-title="Common Tags"
                  @update:value="updateManifest('tags', $event)"
                />
              </section>

              <section v-else-if="detailGroup === 'manifest' && detailSection === 'tools'" class="panel-section">
                <div class="section-title">Shared Tools</div>
                <div class="helper-text">
                  Skill-level tools are shared into every compiled agent node. The backend currently runtime-binds <code>builtin</code> tools and generic <code>api</code> tools; <code>mcp</code> entries are still declarations until an MCP endpoint/config layer is added.
                </div>
                <ObjectListEditor
                  :value="manifest.tools || []"
                  :fields="toolFields"
                  :create-item="createToolItem"
                  help="Declare which tools this skill depends on. Name is the tool id, binding describes the source, and description explains when it is used. For api tools, put config like method/url/body in the description."
                  :presets="toolPresets"
                  preset-title="Quick Add Tools"
                  @update:value="updateManifest('tools', $event)"
                />
              </section>

              <section v-else-if="detailGroup === 'manifest' && detailSection === 'knowledge'" class="panel-section">
                <div class="section-title">Shared Knowledge</div>
                <div class="helper-text">
                  Skill-level knowledge is shared context for the whole skill. During backend compile, it is injected into every agent node and loop-agent body as shared prompt context.
                </div>
                <ObjectListEditor
                  :value="manifest.knowledge || []"
                  :fields="knowledgeFields"
                  :create-item="createKnowledgeItem"
                  help="Knowledge entries describe domain facts, policies, terminology, or reference content the whole skill depends on."
                  :presets="knowledgePresets"
                  preset-title="Quick Add Knowledge"
                  @update:value="updateManifest('knowledge', $event)"
                />
              </section>

              <section v-else-if="detailGroup === 'manifest' && detailSection === 'behavior'" class="panel-section">
                <div class="section-title">Shared Behavior</div>
                <div class="helper-text">
                  Skill-level behavior is shared across all agent nodes and loop-agent bodies. <code>style</code> is a global response style hint, and <code>rules</code> are global behavior constraints.
                </div>
                <BehaviorEditor
                  :value="manifest.behavior || { style: '', rules: [] }"
                  help="Behavior defines how the whole skill should act and present results."
                  :style-suggestions="behaviorStyleSuggestions"
                  :rule-suggestions="behaviorRuleSuggestions"
                  @update:value="updateManifest('behavior', $event)"
                />
              </section>

              <section v-else-if="detailGroup === 'agent' && detailSection === 'basics' && selectedNode?.type === 'agent'" class="panel-section">
                <div class="section-title">Agent Basics</div>
                <label>
                  <span>Label</span>
                  <input :value="selectedNode.label" @input="updateNodeField('label', $event.target.value)" />
                </label>
                <label>
                  <span>Type</span>
                  <input :value="selectedNode.type" disabled />
                </label>

                <div class="summary-metrics">
                  <div v-for="item in selectedNodeSummary" :key="item.label" class="metric-chip">
                    <strong>{{ item.value }}</strong>
                    <span>{{ item.label }}</span>
                  </div>
                </div>
              </section>

              <section v-else-if="detailGroup === 'agent' && detailSection === 'prompt' && selectedNode?.type === 'agent'" class="panel-section">
                <div class="section-title">Agent Prompt</div>
                <label>
                  <span>Instructions</span>
                  <textarea
                    :value="selectedNode.config.instructions || ''"
                    @input="updateNodeConfig('instructions', $event.target.value)"
                  />
                </label>
                <div class="field-help">
                  Recommended format: 2-5 short sentences describing this node's job, required reasoning style, and output expectation. Example: "Analyze the incoming query and produce a structured requirement breakdown. Do not answer the user directly."
                </div>

                <label>
                  <span>Prompt Template</span>
                  <textarea
                    :value="selectedNode.config.prompt_template || ''"
                    @input="updateNodeConfig('prompt_template', $event.target.value)"
                  />
                </label>
                <div class="field-help">
                  Prompt template is plain text with placeholders like <code>{query}</code> and <code>{analysis}</code>. Placeholders should come from this node's <code>pull_keys</code>.
                </div>

                <div v-if="agentPromptWarnings.length" class="warning-block">
                  <div class="warning-title">Prompt Warnings</div>
                  <div v-for="warning in agentPromptWarnings" :key="warning" class="field-help warning-text">
                    {{ warning }}
                  </div>
                </div>
              </section>

              <section v-else-if="detailGroup === 'agent' && detailSection === 'keys' && selectedNode?.type === 'agent'" class="panel-section">
                <div class="section-title">Agent Keys</div>
                <div class="subsection-title">Pull Keys</div>
                <MapEditor
                  :value="selectedNode.config.pull_keys || {}"
                  key-label="Input Key"
                  value-label="Meaning"
                  key-placeholder="query"
                  value-placeholder="Original user request"
                  help="Pull keys tell this node what fields it expects to read."
                  :suggestions="agentPullSuggestions"
                  suggestion-title="Workflow Key Pool"
                  @update:value="updateNodeConfig('pull_keys', $event)"
                />
                <div class="field-help">{{ keyRuleHelp }}</div>
                <div class="field-help">
                  Incoming edge keys are recommendations, not the full definition. MASFactory semantics treat pull_keys as reads from the workflow-level outer attribute scope.
                </div>
                <div v-if="incomingKeyNames.length" class="field-help">
                  Upstream reachable keys for this node: <code>{{ incomingKeyNames.join(', ') }}</code>
                </div>

                <div class="subsection-title">Push Keys</div>
                <MapEditor
                  :value="selectedNode.config.push_keys || {}"
                  key-label="Output Key"
                  value-label="Meaning"
                  key-placeholder="analysis"
                  value-placeholder="Structured task analysis"
                  help="Push keys tell this node what fields it writes back for downstream nodes."
                  :suggestions="agentPushSuggestions"
                  suggestion-title="Workflow Key Pool"
                  @update:value="updateNodeConfig('push_keys', $event)"
                />
                <div class="field-help">
                  Pull keys and push keys do not need to be identical. A node may read <code>query</code> and write <code>analysis</code>; the edge mapping is what connects upstream outputs to downstream inputs.
                </div>
                <div v-if="outgoingKeyNames.length" class="field-help">
                  Downstream edges currently reference: <code>{{ outgoingKeyNames.join(', ') }}</code>
                </div>
              </section>

              <section v-else-if="detailGroup === 'agent' && detailSection === 'capabilities' && selectedNode?.type === 'agent'" class="panel-section">
                <div class="section-title">Agent Capabilities</div>
                <div class="subsection-title">Behavior Rules</div>
                <StringListEditor
                  :value="selectedNode.config.behavior_rules || []"
                  placeholder="Keep the answer concise."
                  help="Each item is one rule that only applies to this node."
                  :suggestions="nodeBehaviorRuleSuggestions"
                  suggestion-title="Common Node Rules"
                  @update:value="updateNodeConfig('behavior_rules', $event)"
                />
                <div class="field-help">
                  Recommended format: one concrete instruction per item. Example: "Only summarize, do not conclude."
                </div>

                <div class="subsection-title">Knowledge</div>
                <ObjectListEditor
                  :value="selectedNode.config.knowledge || []"
                  :fields="knowledgeFields"
                  :create-item="createKnowledgeItem"
                  help="Node-level knowledge only affects this node."
                  :presets="knowledgePresets"
                  preset-title="Quick Add Knowledge"
                  @update:value="updateNodeConfig('knowledge', $event)"
                />
                <div class="field-help">
                  Use node-level knowledge when only this node should see the information. Use skill-level knowledge when every agent-like node should inherit it.
                </div>

                <div class="subsection-title">Tools</div>
                <ObjectListEditor
                  :value="selectedNode.config.tools || []"
                  :fields="toolFields"
                  :create-item="createToolItem"
                  help="Node-level tools only apply to this node. builtin and api bindings are runtime-wired by the backend."
                  :presets="toolPresets"
                  preset-title="Quick Add Tools"
                  @update:value="updateNodeConfig('tools', $event)"
                />
                <div class="field-help">
                  Use node-level tools when a capability belongs to one node only. builtin tools are attached as MASFactory callables, api tools become generic HTTP callables, and mcp entries remain pending external connector support.
                </div>
              </section>

              <section v-else-if="detailGroup === 'custom' && detailSection === 'basics' && selectedNode?.type === 'custom'" class="panel-section">
                <div class="section-title">Custom Node Basics</div>
                <label>
                  <span>Label</span>
                  <input :value="selectedNode.label" @input="updateNodeField('label', $event.target.value)" />
                </label>
                <label>
                  <span>Type</span>
                  <input :value="selectedNode.type" disabled />
                </label>
                <div class="field-help">
                  Open the custom editor to define this node's behavior. Recommended mode: <code>python</code>, where you implement a <code>forward(input_dict, attributes)</code> function for deterministic logic.
                </div>
                <button type="button" @click="$emit('open-custom-editor', selectedNode.id)">Open Custom Editor</button>
              </section>

              <section v-else-if="detailGroup === 'custom' && detailSection === 'runtime' && selectedNode?.type === 'custom'" class="panel-section">
                <div class="section-title">Custom Runtime View</div>
                <div class="object-card">
                  <div class="row-head">Current Mode</div>
                  <div class="field-help"><code>{{ selectedNode.config.mode || 'python' }}</code></div>
                  <div class="field-help">
                    Pull keys: <code>{{ Object.keys(selectedNode.config.pull_keys || {}).join(', ') || 'none' }}</code>
                  </div>
                  <div class="field-help">
                    Push keys: <code>{{ Object.keys(selectedNode.config.push_keys || {}).join(', ') || 'none' }}</code>
                  </div>
                </div>
                <div v-if="incomingKeyNames.length" class="field-help">
                  Upstream reachable keys for this node: <code>{{ incomingKeyNames.join(', ') }}</code>
                </div>
                <div v-if="outgoingKeyNames.length" class="field-help">
                  Downstream edges currently reference: <code>{{ outgoingKeyNames.join(', ') }}</code>
                </div>
              </section>

              <section v-else-if="detailGroup === 'loop' && detailSection === 'basics' && selectedNode?.type === 'loop'" class="panel-section">
                <div class="section-title">Loop Basics</div>
                <label>
                  <span>Label</span>
                  <input :value="selectedNode.label" @input="updateNodeField('label', $event.target.value)" />
                </label>
                <label>
                  <span>Type</span>
                  <input :value="selectedNode.type" disabled />
                </label>
                <div class="summary-metrics">
                  <div v-for="item in selectedNodeSummary" :key="item.label" class="metric-chip">
                    <strong>{{ item.value }}</strong>
                    <span>{{ item.label }}</span>
                  </div>
                </div>
              </section>

              <section v-else-if="detailGroup === 'loop' && detailSection === 'termination' && selectedNode?.type === 'loop'" class="panel-section">
                <div class="section-title">Loop Termination</div>
                <label>
                  <span>Max Iterations</span>
                  <input
                    type="number"
                    min="1"
                    :value="selectedNode.config.max_iterations || 3"
                    @input="updateNodeConfig('max_iterations', Number($event.target.value) || 1)"
                  />
                </label>

                <div class="subsection-title">Terminate Condition</div>
                <label>
                  <span>Mode</span>
                  <select
                    :value="selectedNode.config.terminate_when?.mode || 'never'"
                    @change="updateNestedConfig('terminate_when', 'mode', $event.target.value)"
                  >
                    <option v-for="option in terminateModeOptions" :key="option.value" :value="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label v-if="(selectedNode.config.terminate_when?.mode || 'never') !== 'never'">
                  <span>Key</span>
                  <input
                    :value="selectedNode.config.terminate_when?.key || ''"
                    @input="updateNestedConfig('terminate_when', 'key', $event.target.value)"
                  />
                </label>
                <label v-if="selectedNode.config.terminate_when?.mode === 'key_equals'">
                  <span>Value</span>
                  <input
                    :value="selectedNode.config.terminate_when?.value ?? true"
                    @input="updateNestedConfig('terminate_when', 'value', $event.target.value)"
                  />
                </label>
              </section>

              <section v-else-if="detailGroup === 'loop' && detailSection === 'structure' && selectedNode?.type === 'loop'" class="panel-section">
                <div class="section-title">Loop Structure</div>
                <div class="field-help">
                  Loop internals live in a dedicated editor. Open the loop editor to design inner nodes, inner edges, controller inputs, and controller outputs like a real MASFactory loop subgraph.
                </div>
                <div class="field-help">
                  Current inner graph: {{ (selectedNode.config.subgraph?.nodes || []).length }} nodes,
                  {{ (selectedNode.config.subgraph?.edges || []).length }} inner edges,
                  {{ (selectedNode.config.controller_inputs || []).length }} controller inputs,
                  {{ (selectedNode.config.controller_outputs || []).length }} controller outputs.
                </div>
                <button type="button" @click="$emit('open-loop-editor', selectedNode.id)">Open Loop Editor</button>
              </section>

              <section v-else-if="detailGroup === 'node' && detailSection === 'basics' && selectedNode" class="panel-section">
                <div class="section-title">Node Basics</div>
                <label>
                  <span>Label</span>
                  <input :value="selectedNode.label" @input="updateNodeField('label', $event.target.value)" />
                </label>
                <label>
                  <span>Type</span>
                  <input :value="selectedNode.type" disabled />
                </label>
              </section>
            </main>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
