<script setup>
import { computed } from 'vue';
import BehaviorEditor from './BehaviorEditor.vue';
import MapEditor from './MapEditor.vue';
import ObjectListEditor from './ObjectListEditor.vue';
import StringListEditor from './StringListEditor.vue';

const props = defineProps({
  selectedNode: { type: Object, default: null },
  manifest: { type: Object, required: true },
  document: { type: Object, required: true }
});

const emit = defineEmits(['update-node', 'update-manifest', 'delete-node']);

const toolFields = [
  { key: 'name', label: 'Name', placeholder: 'web_search' },
  {
    key: 'binding',
    label: 'Binding',
    options: [
      { value: 'mcp', label: 'mcp' },
      { value: 'builtin', label: 'builtin' },
      { value: 'api', label: 'api' },
      { value: 'other', label: 'other' }
    ],
    help: 'Binding means how this tool is connected at runtime. mcp = MASFactory/MCP tool, builtin = built into the runtime or app, api = external HTTP/API service, other = reserved custom integration.'
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
    label: 'Web Search',
    description: 'Search the web for supporting information',
    item: { name: 'web_search', binding: 'mcp', description: 'Searches the web for supporting evidence.' }
  },
  {
    label: 'HTTP API',
    description: 'Call an external API service',
    item: { name: 'http_api', binding: 'api', description: 'Calls an external HTTP API.' }
  },
  {
    label: 'Retriever',
    description: 'Lookup internal documents or vector data',
    item: { name: 'retriever', binding: 'builtin', description: 'Retrieves internal reference material.' }
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
  mergeSuggestions(selectedIncomingSuggestions.value, [
    { key: 'query', value: 'Original user request' },
    { key: 'message', value: 'Input message' },
    { key: 'context', value: 'Relevant context' }
  ])
);

const agentPushSuggestions = computed(() =>
  mergeSuggestions(selectedOutgoingSuggestions.value, [
    { key: 'answer', value: 'Main answer' },
    { key: 'analysis', value: 'Structured analysis' },
    { key: 'summary', value: 'Short summary' }
  ])
);

const customPullSuggestions = computed(() =>
  mergeSuggestions(selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Input message' },
    { key: 'analysis', value: 'Structured analysis' },
    { key: 'context', value: 'Additional context' }
  ])
);

const customPushSuggestions = computed(() =>
  mergeSuggestions(selectedOutgoingSuggestions.value, [
    { key: 'message', value: 'Output message' },
    { key: 'result', value: 'Transformed result' },
    { key: 'summary', value: 'Formatted summary' }
  ])
);

const loopInputSuggestions = computed(() =>
  mergeSuggestions(selectedIncomingSuggestions.value, [
    { key: 'message', value: 'Loop input' },
    { key: 'query', value: 'Task to iterate on' }
  ])
);

const loopOutputSuggestions = computed(() =>
  mergeSuggestions(selectedOutgoingSuggestions.value, [
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
    mappingSuggestions(props.selectedNode?.config?.body?.output_mapping || {}),
    mappingSuggestions(props.selectedNode?.config?.push_keys || {}),
    loopOutputSuggestions.value
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
        Skill-level tools describe capabilities the whole skill depends on. In the current MVP they are exported as manifest metadata. Runtime auto-binding is not finished yet, so use `binding` mainly as declaration.
      </div>
      <ObjectListEditor
        :value="manifest.tools || []"
        :fields="toolFields"
        :create-item="createToolItem"
        help="Declare which tools this skill depends on. Name is the tool id, binding describes the source, description explains when it is used."
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

          <div class="subsection-title">Pull Keys</div>
          <MapEditor
            :value="selectedNode.config.pull_keys || {}"
            key-label="Input Key"
            value-label="Meaning"
            key-placeholder="query"
            value-placeholder="Original user request"
            help="Pull keys tell this node what fields it expects to read."
            :suggestions="agentPullSuggestions"
            suggestion-title="From Incoming Edges"
            @update:value="updateNodeConfig('pull_keys', $event)"
          />
          <div class="field-help">{{ keyRuleHelp }}</div>

          <div class="subsection-title">Push Keys</div>
          <MapEditor
            :value="selectedNode.config.push_keys || {}"
            key-label="Output Key"
            value-label="Meaning"
            key-placeholder="analysis"
            value-placeholder="Structured task analysis"
            help="Push keys tell this node what fields it writes back for downstream nodes."
            :suggestions="agentPushSuggestions"
            suggestion-title="For Downstream Nodes"
            @update:value="updateNodeConfig('push_keys', $event)"
          />
          <div class="field-help">
            Pull keys and push keys do not need to be identical. A node may read <code>query</code> and write <code>analysis</code>; the edge mapping is what connects upstream outputs to downstream inputs.
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
            help="Node-level tools are only declared for this node."
            :presets="toolPresets"
            preset-title="Quick Add Tools"
            @update:value="updateNodeConfig('tools', $event)"
          />
          <div class="field-help">
            Use node-level tools when a capability belongs to one node only. In the current MVP, tool declarations are metadata and export information; automatic runtime tool wiring is not complete yet.
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
            suggestion-title="Suggested Outputs"
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
            suggestion-title="Suggested Outputs"
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
            suggestion-title="From Incoming Edges"
            @update:value="updateNodeConfig('pull_keys', $event)"
          />
          <div class="field-help">{{ keyRuleHelp }}</div>

          <div class="subsection-title">Push Keys</div>
          <MapEditor
            :value="selectedNode.config.push_keys || {}"
            key-label="Output Key"
            value-label="Meaning"
            key-placeholder="analysis_card"
            value-placeholder="Formatted analysis card"
            :suggestions="customPushSuggestions"
            suggestion-title="For Downstream Nodes"
            @update:value="updateNodeConfig('push_keys', $event)"
          />
          <div class="field-help">
            Custom nodes may transform key names. Example: read <code>analysis</code>, write <code>summary_card</code>.
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
          <div v-if="loopBodyOutputSuggestions.length" class="suggestion-strip compact">
            <div class="suggestion-title">Suggested Stop Keys</div>
            <div class="suggestion-list">
              <button
                v-for="suggestion in loopBodyOutputSuggestions"
                :key="suggestion.key"
                type="button"
                class="suggestion-chip"
                @click="updateNestedConfig('terminate_when', 'key', suggestion.key)"
              >
                <span>{{ suggestion.key }}</span>
                <small v-if="suggestion.value">{{ suggestion.value }}</small>
              </button>
            </div>
          </div>
          <label v-if="selectedNode.config.terminate_when?.mode === 'key_equals'">
            <span>Value</span>
            <input
              :value="selectedNode.config.terminate_when?.value ?? true"
              @input="updateNestedConfig('terminate_when', 'value', $event.target.value)"
            />
          </label>

          <div class="subsection-title">Body Type</div>
          <label>
            <span>Type</span>
            <select
              :value="selectedNode.config.body?.type || 'agent'"
              @change="updateNestedConfig('body', 'type', $event.target.value)"
            >
              <option v-for="option in loopBodyTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <div class="subsection-title">Body Input Mapping</div>
          <MapEditor
            :value="selectedNode.config.body?.input_mapping || {}"
            key-label="Loop Body Input"
            value-label="Meaning"
            key-placeholder="message"
            value-placeholder="Loop input"
            :suggestions="loopInputSuggestions"
            suggestion-title="From Incoming Edges"
            @update:value="updateNestedConfig('body', 'input_mapping', $event)"
          />

          <div class="subsection-title">Body Output Mapping</div>
          <MapEditor
            :value="selectedNode.config.body?.output_mapping || {}"
            key-label="Loop Body Output"
            value-label="Meaning"
            key-placeholder="done"
            value-placeholder="Stop flag"
            :suggestions="loopOutputSuggestions"
            suggestion-title="For Downstream Nodes"
            @update:value="updateNestedConfig('body', 'output_mapping', $event)"
          />

          <template v-if="(selectedNode.config.body?.type || 'agent') === 'agent'">
            <label>
              <span>Body Instructions</span>
              <textarea
                :value="selectedNode.config.body?.instructions || ''"
                @input="updateNestedConfig('body', 'instructions', $event.target.value)"
              />
            </label>
            <div class="field-help">
              Same recommendation as agent instructions: describe what one loop iteration should do and what counts as completion.
            </div>
            <label>
              <span>Body Prompt Template</span>
              <textarea
                :value="selectedNode.config.body?.prompt_template || ''"
                @input="updateNestedConfig('body', 'prompt_template', $event.target.value)"
              />
            </label>
            <div class="field-help">
              Use placeholders from body <code>pull_keys</code> or body <code>input_mapping</code>, for example <code>Current state: {message}</code>.
            </div>
            <div class="subsection-title">Body Pull Keys</div>
            <MapEditor
              :value="selectedNode.config.body?.pull_keys || {}"
              key-label="Input Key"
              value-label="Meaning"
              :suggestions="loopBodyInputSuggestions"
              suggestion-title="Body Input Suggestions"
              @update:value="updateNestedConfig('body', 'pull_keys', $event)"
            />
            <div class="subsection-title">Body Push Keys</div>
            <MapEditor
              :value="selectedNode.config.body?.push_keys || {}"
              key-label="Output Key"
              value-label="Meaning"
              :suggestions="loopBodyOutputSuggestions"
              suggestion-title="Body Output Suggestions"
              @update:value="updateNestedConfig('body', 'push_keys', $event)"
            />
            <div class="field-help">{{ keyRuleHelp }}</div>
            <div class="subsection-title">Body Behavior Rules</div>
            <StringListEditor
              :value="selectedNode.config.body?.behavior_rules || []"
              placeholder="Return one iteration update."
              :suggestions="nodeBehaviorRuleSuggestions"
              suggestion-title="Common Node Rules"
              @update:value="updateNestedConfig('body', 'behavior_rules', $event)"
            />
            <div class="subsection-title">Body Knowledge</div>
            <ObjectListEditor
              :value="selectedNode.config.body?.knowledge || []"
              :fields="knowledgeFields"
              :create-item="createKnowledgeItem"
              :presets="knowledgePresets"
              preset-title="Quick Add Knowledge"
              @update:value="updateNestedConfig('body', 'knowledge', $event)"
            />
            <div class="subsection-title">Body Tools</div>
            <ObjectListEditor
              :value="selectedNode.config.body?.tools || []"
              :fields="toolFields"
              :create-item="createToolItem"
              :presets="toolPresets"
              preset-title="Quick Add Tools"
              @update:value="updateNestedConfig('body', 'tools', $event)"
            />
          </template>

          <template v-else>
            <label>
              <span>Body Custom Mode</span>
              <select
                :value="selectedNode.config.body?.mode || 'passthrough'"
                @change="updateNestedConfig('body', 'mode', $event.target.value)"
              >
                <option v-for="option in customModeOptions" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <div v-if="(selectedNode.config.body?.mode || 'passthrough') === 'template'" class="subsection-title">Body Templates</div>
            <MapEditor
              v-if="(selectedNode.config.body?.mode || 'passthrough') === 'template'"
              :value="selectedNode.config.body?.templates || {}"
              key-label="Output Key"
              value-label="Template"
              :suggestions="loopBodyOutputSuggestions"
              @update:value="updateNestedConfig('body', 'templates', $event)"
            />
            <div v-if="selectedNode.config.body?.mode === 'set'" class="subsection-title">Body Static Outputs</div>
            <MapEditor
              v-if="selectedNode.config.body?.mode === 'set'"
              :value="selectedNode.config.body?.static_outputs || {}"
              key-label="Output Key"
              value-label="Static Value"
              :suggestions="loopBodyOutputSuggestions"
              @update:value="updateNestedConfig('body', 'static_outputs', $event)"
            />
            <div v-if="selectedNode.config.body?.mode === 'pick'" class="subsection-title">Body Pick Keys</div>
            <MapEditor
              v-if="selectedNode.config.body?.mode === 'pick'"
              :value="selectedNode.config.body?.pick_keys || {}"
              key-label="Output Key"
              value-label="Source Key"
              :suggestions="loopBodyInputSuggestions"
              suggestion-value-mode="key"
              @update:value="updateNestedConfig('body', 'pick_keys', $event)"
            />
            <div class="field-help">
              In pick mode, the left side is the new output key and the right side is an existing input key to copy from.
            </div>
          </template>
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
