<script setup>
import { computed } from 'vue';
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

const emit = defineEmits(['update-node', 'update-manifest', 'delete-node', 'open-loop-editor']);

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
const customModeOptions = [
  { value: 'passthrough', label: 'Passthrough' },
  { value: 'template', label: 'Template' },
  { value: 'set', label: 'Set Static Values' },
  { value: 'pick', label: 'Pick Inputs' }
];
const terminateModeOptions = [
  { value: 'never', label: 'Never Stop Early' },
  { value: 'key_truthy', label: 'Stop When Key Is Truthy' },
  { value: 'key_equals', label: 'Stop When Key Equals Value' }
];
const loopBodyTypeOptions = [
  { value: 'agent', label: 'Agent Body' },
  { value: 'custom', label: 'Custom Body' }
];
const keyRuleHelp =
  'Key names are identifiers like query, analysis_result, answer, done. Use lowercase letters, numbers, and underscores when possible. Nodes may define new keys; edges map one node output key to another node input key.';

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

const customPullSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Input message' },
    { key: 'analysis', value: 'Structured analysis' },
    { key: 'context', value: 'Additional context' }
  ])
);

const customPushSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedOutgoingSuggestions.value, [
    { key: 'message', value: 'Output message' },
    { key: 'result', value: 'Transformed result' },
    { key: 'summary', value: 'Formatted summary' }
  ])
);

const loopInputSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Loop input' },
    { key: 'query', value: 'Task to iterate on' }
  ])
);

const loopOutputSuggestions = computed(() =>
  mergeSuggestions(globalKeySuggestions.value, selectedOutgoingSuggestions.value, [
    { key: 'message', value: 'Loop output' },
    { key: 'done', value: 'Stop flag' },
    { key: 'result', value: 'Final result' }
  ])
);

const loopBodyInputSuggestions = computed(() =>
  mergeSuggestions(
    mappingSuggestions(props.selectedNode?.config?.body?.input_mapping || {}),
    mappingSuggestions(props.selectedNode?.config?.pull_keys || {}),
    loopInputSuggestions.value
  )
);

const loopBodyOutputSuggestions = computed(() =>
  mergeSuggestions(
    globalKeySuggestions.value,
    mappingSuggestions(props.selectedNode?.config?.body?.output_mapping || {}),
    mappingSuggestions(props.selectedNode?.config?.push_keys || {}),
    loopOutputSuggestions.value
  )
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
  return extractPlaceholders(promptTemplate).map((key) => {
    if (allowed.has(key)) {
      return null;
    }
    if (global.has(key)) {
      return `${scopeLabel}: {${key}} is in workflow key pool but missing from pull_keys.`;
    }
    return `${scopeLabel}: {${key}} cannot be found in pull_keys or workflow key pool.`;
  }).filter(Boolean);
}

const agentPromptWarnings = computed(() =>
  promptWarnings(
    props.selectedNode?.config?.prompt_template || '',
    props.selectedNode?.config?.pull_keys || {},
    props.keyPool?.key_names || [],
    'Prompt template'
  )
);

const loopBodyPromptWarnings = computed(() =>
  promptWarnings(
    props.selectedNode?.config?.body?.prompt_template || '',
    props.selectedNode?.config?.body?.pull_keys || props.selectedNode?.config?.body?.input_mapping || {},
    props.keyPool?.key_names || [],
    'Loop body prompt template'
  )
);
</script>

<template>
  <div class="inspector-panel">
    <section class="panel-section">
      <div class="section-title">Skill Manifest</div>
      <div class="field-help">
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

      <div class="subsection-title">Tags</div>
      <StringListEditor
        :value="manifest.tags || []"
        placeholder="faq / customer-service / workflow"
        help="Tags are short labels used for search and categorization."
        :suggestions="tagSuggestions"
        suggestion-title="Common Tags"
        @update:value="updateManifest('tags', $event)"
      />

      <div class="subsection-title">Tools</div>
      <div class="field-help">
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

      <div class="subsection-title">Knowledge</div>
      <div class="field-help">
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

      <div class="subsection-title">Behavior</div>
      <div class="field-help">
        Skill-level behavior is also shared across all agent nodes and loop-agent bodies. `style` is a global response style hint, and `rules` are global behavior constraints.
      </div>
      <BehaviorEditor
        :value="manifest.behavior || { style: '', rules: [] }"
        help="Behavior defines how the whole skill should act and present results."
        :style-suggestions="behaviorStyleSuggestions"
        :rule-suggestions="behaviorRuleSuggestions"
        @update:value="updateManifest('behavior', $event)"
      />
    </section>

    <section class="panel-section">
      <div class="section-title">Selected Node</div>
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
          <div class="field-help">Incoming edge keys are recommendations, not the full definition. MASFactory semantics treat pull_keys as reads from the workflow-level outer attribute scope.</div>
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
        </template>

        <template v-else-if="selectedNode.type === 'custom'">
          <label>
            <span>Mode</span>
            <select
              :value="selectedNode.config.mode || 'passthrough'"
              @change="updateNodeConfig('mode', $event.target.value)"
            >
              <option v-for="option in customModeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <div class="field-help">
            <code>template</code> generates text with placeholders like <code>{analysis}</code>.
            <code>set</code> writes fixed values. <code>pick</code> copies selected input keys.
            <code>passthrough</code> forwards inputs directly.
          </div>

          <div v-if="(selectedNode.config.mode || 'passthrough') === 'template'" class="subsection-title">Templates</div>
          <MapEditor
            v-if="(selectedNode.config.mode || 'passthrough') === 'template'"
            :value="selectedNode.config.templates || {}"
            key-label="Output Key"
            value-label="Template"
            key-placeholder="summary"
            value-placeholder="Summary: {analysis}"
            help="Used in template mode. Values may reference input fields with {field_name}."
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
            key-placeholder="message"
            value-placeholder="ok"
            help="Used in set mode. Every row becomes a fixed output field."
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
            key-placeholder="result"
            value-placeholder="analysis"
            help="Used in pick mode. Maps output key to an input key."
            :suggestions="customPullSuggestions"
            suggestion-title="Suggested Source Keys"
            suggestion-value-mode="key"
            @update:value="updateNodeConfig('pick_keys', $event)"
          />

          <div class="subsection-title">Pull Keys</div>
          <MapEditor
            :value="selectedNode.config.pull_keys || {}"
            key-label="Input Key"
            value-label="Meaning"
            key-placeholder="analysis"
            value-placeholder="Structured workflow analysis"
            :suggestions="customPullSuggestions"
            suggestion-title="Workflow Key Pool"
            @update:value="updateNodeConfig('pull_keys', $event)"
          />
          <div class="field-help">{{ keyRuleHelp }}</div>
          <div v-if="incomingKeyNames.length" class="field-help">
            Upstream reachable keys for this node: <code>{{ incomingKeyNames.join(', ') }}</code>
          </div>

          <div class="subsection-title">Push Keys</div>
          <MapEditor
            :value="selectedNode.config.push_keys || {}"
            key-label="Output Key"
            value-label="Meaning"
            key-placeholder="analysis_card"
            value-placeholder="Formatted analysis card"
            :suggestions="customPushSuggestions"
            suggestion-title="Workflow Key Pool"
            @update:value="updateNodeConfig('push_keys', $event)"
          />
          <div class="field-help">
            Custom nodes may transform key names. Example: read <code>analysis</code>, write <code>summary_card</code>.
          </div>
          <div v-if="outgoingKeyNames.length" class="field-help">
            Downstream edges currently reference: <code>{{ outgoingKeyNames.join(', ') }}</code>
          </div>
        </template>

        <template v-else-if="selectedNode.type === 'loop'">
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
          <div class="field-help">
            Loop internals now live in a dedicated editor. Open the loop editor to design inner nodes, inner edges, controller inputs, and controller outputs like a real MASFactory loop subgraph.
          </div>
          <div class="field-help">
            Current inner graph: {{ (selectedNode.config.subgraph?.nodes || []).length }} nodes,
            {{ (selectedNode.config.subgraph?.edges || []).length }} inner edges,
            {{ (selectedNode.config.controller_inputs || []).length }} controller inputs,
            {{ (selectedNode.config.controller_outputs || []).length }} controller outputs.
          </div>
          <button type="button" @click="$emit('open-loop-editor', selectedNode.id)">Edit Loop</button>
        </template>

        <button
          v-if="selectedNode.type !== 'start' && selectedNode.type !== 'end'"
          type="button"
          class="danger-button"
          @click="$emit('delete-node', selectedNode.id)"
        >
          Delete Node
        </button>
      </template>
      <p v-else class="empty-state">
        Select a node on the canvas to edit it.
      </p>
    </section>
  </div>
</template>
