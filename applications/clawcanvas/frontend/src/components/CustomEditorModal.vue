<script setup>
import { computed } from 'vue';
import MapEditor from './MapEditor.vue';

const props = defineProps({
  customNode: { type: Object, required: true },
  keyPool: { type: Object, required: true }
});

const emit = defineEmits(['close', 'rename-custom', 'update-custom-config']);

const modeOptions = [
  { value: 'python', label: 'Python Logic' },
  { value: 'compose', label: 'Compose Mixed Output' },
  { value: 'template', label: 'Template' },
  { value: 'set', label: 'Set Static Values' },
  { value: 'pick', label: 'Pick Inputs' },
  { value: 'passthrough', label: 'Passthrough' }
];

const starterPython = `def forward(input_dict, attributes):
    """
    input_dict: current edge message payload
    attributes: workflow-level / node-level visible attributes
    return: dict payload for downstream edges
    """
    query = input_dict.get("query") or input_dict.get("message", "")
    return {
        "message": f"processed: {query}",
        "length": len(str(query)),
    }
`;

const globalSuggestions = computed(() =>
  Object.entries(props.keyPool?.key_map || {}).map(([key, value]) => ({
    key: String(key),
    value: String(value ?? '')
  }))
);

function updateConfig(field, value) {
  emit('update-custom-config', {
    id: props.customNode.id,
    config: {
      ...props.customNode.config,
      [field]: value
    }
  });
}

function ensurePythonStarter() {
  if (String(props.customNode.config?.python_code || '').trim()) return;
  updateConfig('python_code', starterPython);
}

function updateMode(value) {
  updateConfig('mode', value);
  if (value === 'python') {
    ensurePythonStarter();
  }
}
</script>

<template>
  <div class="loop-modal-backdrop" @click.self="$emit('close')">
    <div class="loop-modal-shell custom-modal-shell">
      <header class="loop-modal-header">
        <div>
          <div class="eyebrow">Custom Node Editor</div>
          <h2>{{ customNode.label }}</h2>
          <p>Edit this custom node in a dedicated view. Python mode is the primary path when you want user-written node logic without LLM execution.</p>
        </div>
        <button type="button" class="ghost" @click="$emit('close')">Close</button>
      </header>

      <div class="loop-modal-grid custom-modal-grid">
        <aside class="loop-modal-sidebar">
          <section class="panel-section">
            <div class="section-title">Node Identity</div>
            <label>
              <span>Label</span>
              <input :value="customNode.label" @input="$emit('rename-custom', { id: customNode.id, label: $event.target.value })" />
            </label>
            <label>
              <span>Mode</span>
              <select :value="customNode.config.mode || 'python'" @change="updateMode($event.target.value)">
                <option v-for="option in modeOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>
            <div class="field-help">
              `python` means this node is executed by your own Python code. It does not call the model unless your code explicitly does so.
            </div>
          </section>

          <section class="panel-section">
            <div class="section-title">Node Keys</div>
            <div class="subsection-title">Pull Keys</div>
            <MapEditor
              :value="customNode.config.pull_keys || {}"
              key-label="Input Key"
              value-label="Meaning"
              key-placeholder="query"
              value-placeholder="Input available to Python code"
              help="These fields are available in input_dict and outer attribute scope."
              :suggestions="globalSuggestions"
              suggestion-title="Workflow Key Pool"
              @update:value="updateConfig('pull_keys', $event)"
            />
            <div class="subsection-title">Push Keys</div>
            <MapEditor
              :value="customNode.config.push_keys || {}"
              key-label="Output Key"
              value-label="Meaning"
              key-placeholder="result"
              value-placeholder="Output produced by Python code"
              help="Your forward function should usually return these keys for downstream nodes."
              :suggestions="globalSuggestions"
              suggestion-title="Workflow Key Pool"
              @update:value="updateConfig('push_keys', $event)"
            />
          </section>

          <section v-if="['template', 'compose'].includes(customNode.config.mode || 'python')" class="panel-section">
            <div class="section-title">Templates</div>
            <MapEditor
              :value="customNode.config.templates || {}"
              key-label="Output Key"
              value-label="Template"
              key-placeholder="summary"
              value-placeholder="Summary: {message}"
              :suggestions="globalSuggestions"
              suggestion-title="Workflow Key Pool"
              @update:value="updateConfig('templates', $event)"
            />
          </section>

          <section v-if="['set', 'compose'].includes(customNode.config.mode || 'python')" class="panel-section">
            <div class="section-title">Static Outputs</div>
            <MapEditor
              :value="customNode.config.static_outputs || {}"
              key-label="Output Key"
              value-label="Static Value"
              key-placeholder="status"
              value-placeholder="ready"
              :suggestions="globalSuggestions"
              suggestion-title="Workflow Key Pool"
              @update:value="updateConfig('static_outputs', $event)"
            />
          </section>

          <section v-if="['pick', 'compose'].includes(customNode.config.mode || 'python')" class="panel-section">
            <div class="section-title">Pick Keys</div>
            <MapEditor
              :value="customNode.config.pick_keys || {}"
              key-label="Output Key"
              value-label="Source Key"
              key-placeholder="copied_query"
              value-placeholder="query"
              :suggestions="globalSuggestions"
              suggestion-title="Workflow Key Pool"
              suggestion-value-mode="key"
              @update:value="updateConfig('pick_keys', $event)"
            />
          </section>
        </aside>

        <main class="custom-modal-main">
          <section class="panel-section custom-code-panel">
            <div class="section-title">Python Logic</div>
            <div class="field-help">
              Define a function named <code>forward</code>. Supported signatures follow MASFactory <code>CustomNode</code>, but the recommended form is:
            </div>
            <pre class="code-hint">def forward(input_dict, attributes) -> dict:</pre>
            <div class="field-help">
              `input_dict` is this node's incoming message. `attributes` is the visible outer scope. Return a dict for downstream edges.
            </div>
            <textarea
              class="custom-code-editor"
              :value="customNode.config.python_code || starterPython"
              spellcheck="false"
              @input="updateConfig('python_code', $event.target.value)"
            />
          </section>
        </main>
      </div>
    </div>
  </div>
</template>
