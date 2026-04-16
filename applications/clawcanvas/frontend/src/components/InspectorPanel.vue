<script setup>
const props = defineProps({
  selectedNode: { type: Object, default: null },
  manifest: { type: Object, required: true }
});

const emit = defineEmits(['update-node', 'update-manifest', 'delete-node']);

function updateNodeField(field, value) {
  if (!props.selectedNode) return;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: { [field]: value }
  });
}

function parseJsonOrFallback(raw, fallback) {
  try {
    return raw ? JSON.parse(raw) : Array.isArray(fallback) ? [] : {};
  } catch {
    return fallback;
  }
}

function updateNodeConfig(field, value, parseJson = false) {
  if (!props.selectedNode) return;
  const nextValue = parseJson ? parseJsonOrFallback(value, props.selectedNode.config[field]) : value;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: {
      config: {
        ...props.selectedNode.config,
        [field]: nextValue
      }
    }
  });
}

function updateNestedConfig(rootField, field, value, parseJson = false) {
  if (!props.selectedNode) return;
  const root = props.selectedNode.config[rootField] || {};
  const nextValue = parseJson ? parseJsonOrFallback(value, root[field]) : value;
  emit('update-node', {
    id: props.selectedNode.id,
    patch: {
      config: {
        ...props.selectedNode.config,
        [rootField]: {
          ...root,
          [field]: nextValue
        }
      }
    }
  });
}

function updateManifest(field, value, parseJson = false) {
  const nextValue = parseJson ? parseJsonOrFallback(value, props.manifest[field]) : value;
  emit('update-manifest', { [field]: nextValue });
}
</script>

<template>
  <div class="inspector-panel">
    <section class="panel-section">
      <div class="section-title">Skill Manifest</div>
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
      <label>
        <span>Tags JSON</span>
        <textarea :value="JSON.stringify(manifest.tags, null, 2)" @input="updateManifest('tags', $event.target.value, true)" />
      </label>
      <label>
        <span>Tools JSON</span>
        <textarea :value="JSON.stringify(manifest.tools, null, 2)" @input="updateManifest('tools', $event.target.value, true)" />
      </label>
      <label>
        <span>Knowledge JSON</span>
        <textarea :value="JSON.stringify(manifest.knowledge, null, 2)" @input="updateManifest('knowledge', $event.target.value, true)" />
      </label>
      <label>
        <span>Behavior JSON</span>
        <textarea :value="JSON.stringify(manifest.behavior, null, 2)" @input="updateManifest('behavior', $event.target.value, true)" />
      </label>
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
            <textarea :value="selectedNode.config.instructions || ''" @input="updateNodeConfig('instructions', $event.target.value)" />
          </label>
          <label>
            <span>Prompt Template</span>
            <textarea :value="selectedNode.config.prompt_template || ''" @input="updateNodeConfig('prompt_template', $event.target.value)" />
          </label>
          <label>
            <span>Pull Keys JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.pull_keys || {}, null, 2)" @input="updateNodeConfig('pull_keys', $event.target.value, true)" />
          </label>
          <label>
            <span>Push Keys JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.push_keys || {}, null, 2)" @input="updateNodeConfig('push_keys', $event.target.value, true)" />
          </label>
          <label>
            <span>Behavior Rules JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.behavior_rules || [], null, 2)" @input="updateNodeConfig('behavior_rules', $event.target.value, true)" />
          </label>
          <label>
            <span>Knowledge JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.knowledge || [], null, 2)" @input="updateNodeConfig('knowledge', $event.target.value, true)" />
          </label>
          <label>
            <span>Tools JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.tools || [], null, 2)" @input="updateNodeConfig('tools', $event.target.value, true)" />
          </label>
        </template>

        <template v-else-if="selectedNode.type === 'custom'">
          <label>
            <span>Mode</span>
            <input :value="selectedNode.config.mode || 'passthrough'" @input="updateNodeConfig('mode', $event.target.value)" />
          </label>
          <label>
            <span>Templates JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.templates || {}, null, 2)" @input="updateNodeConfig('templates', $event.target.value, true)" />
          </label>
          <label>
            <span>Static Outputs JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.static_outputs || {}, null, 2)" @input="updateNodeConfig('static_outputs', $event.target.value, true)" />
          </label>
          <label>
            <span>Pick Keys JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.pick_keys || {}, null, 2)" @input="updateNodeConfig('pick_keys', $event.target.value, true)" />
          </label>
          <label>
            <span>Pull Keys JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.pull_keys || {}, null, 2)" @input="updateNodeConfig('pull_keys', $event.target.value, true)" />
          </label>
          <label>
            <span>Push Keys JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.push_keys || {}, null, 2)" @input="updateNodeConfig('push_keys', $event.target.value, true)" />
          </label>
        </template>

        <template v-else-if="selectedNode.type === 'loop'">
          <label>
            <span>Max Iterations</span>
            <input :value="selectedNode.config.max_iterations || 3" @input="updateNodeConfig('max_iterations', Number($event.target.value) || 1)" />
          </label>
          <label>
            <span>Terminate Mode</span>
            <input :value="selectedNode.config.terminate_when?.mode || 'never'" @input="updateNestedConfig('terminate_when', 'mode', $event.target.value)" />
          </label>
          <label>
            <span>Terminate Key</span>
            <input :value="selectedNode.config.terminate_when?.key || ''" @input="updateNestedConfig('terminate_when', 'key', $event.target.value)" />
          </label>
          <label>
            <span>Terminate Value JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.terminate_when?.value ?? true, null, 2)" @input="updateNestedConfig('terminate_when', 'value', $event.target.value, true)" />
          </label>
          <label>
            <span>Body Type</span>
            <input :value="selectedNode.config.body?.type || 'agent'" @input="updateNestedConfig('body', 'type', $event.target.value)" />
          </label>
          <label>
            <span>Body Input Mapping JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.body?.input_mapping || {}, null, 2)" @input="updateNestedConfig('body', 'input_mapping', $event.target.value, true)" />
          </label>
          <label>
            <span>Body Output Mapping JSON</span>
            <textarea :value="JSON.stringify(selectedNode.config.body?.output_mapping || {}, null, 2)" @input="updateNestedConfig('body', 'output_mapping', $event.target.value, true)" />
          </label>
          <template v-if="(selectedNode.config.body?.type || 'agent') === 'agent'">
            <label>
              <span>Body Instructions</span>
              <textarea :value="selectedNode.config.body?.instructions || ''" @input="updateNestedConfig('body', 'instructions', $event.target.value)" />
            </label>
            <label>
              <span>Body Prompt Template</span>
              <textarea :value="selectedNode.config.body?.prompt_template || ''" @input="updateNestedConfig('body', 'prompt_template', $event.target.value)" />
            </label>
            <label>
              <span>Body Pull Keys JSON</span>
              <textarea :value="JSON.stringify(selectedNode.config.body?.pull_keys || {}, null, 2)" @input="updateNestedConfig('body', 'pull_keys', $event.target.value, true)" />
            </label>
            <label>
              <span>Body Push Keys JSON</span>
              <textarea :value="JSON.stringify(selectedNode.config.body?.push_keys || {}, null, 2)" @input="updateNestedConfig('body', 'push_keys', $event.target.value, true)" />
            </label>
          </template>
          <template v-else>
            <label>
              <span>Body Custom Mode</span>
              <input :value="selectedNode.config.body?.mode || 'passthrough'" @input="updateNestedConfig('body', 'mode', $event.target.value)" />
            </label>
            <label>
              <span>Body Templates JSON</span>
              <textarea :value="JSON.stringify(selectedNode.config.body?.templates || {}, null, 2)" @input="updateNestedConfig('body', 'templates', $event.target.value, true)" />
            </label>
            <label>
              <span>Body Static Outputs JSON</span>
              <textarea :value="JSON.stringify(selectedNode.config.body?.static_outputs || {}, null, 2)" @input="updateNestedConfig('body', 'static_outputs', $event.target.value, true)" />
            </label>
            <label>
              <span>Body Pick Keys JSON</span>
              <textarea :value="JSON.stringify(selectedNode.config.body?.pick_keys || {}, null, 2)" @input="updateNestedConfig('body', 'pick_keys', $event.target.value, true)" />
            </label>
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
