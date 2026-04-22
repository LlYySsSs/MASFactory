<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  keyPool: { type: Object, required: true }
});

const emit = defineEmits(['update-key-pool', 'rename-key']);

const pendingNames = ref({});
const newKeyName = ref('');
const newKeyDescription = ref('');

const sortedKeys = computed(() => props.keyPool.keys || []);

function updateDescription(key, description) {
  emit('update-key-pool', {
    ...(props.keyPool.key_map || {}),
    [key]: description
  });
}

function commitRename(oldKey) {
  const nextName = String(pendingNames.value[oldKey] || oldKey).trim();
  if (!nextName || nextName === oldKey) return;
  emit('rename-key', { oldKey, newKey: nextName });
  pendingNames.value = {
    ...pendingNames.value,
    [oldKey]: nextName
  };
}

function addKey() {
  const key = String(newKeyName.value || '').trim();
  if (!key) return;
  emit('update-key-pool', {
    ...(props.keyPool.key_map || {}),
    [key]: String(newKeyDescription.value || '')
  });
  newKeyName.value = '';
  newKeyDescription.value = '';
}
</script>

<template>
  <section class="tool-group">
    <div class="group-title">Workflow Keys</div>
    <div class="field-help">
      This is the workflow-level key pool. It aggregates keys from document inputs, workflow attributes, key metadata, node pull/push keys, and edge mappings. Pull keys should choose from here first. Push keys may create new keys here for the rest of the workflow to use.
    </div>
    <div class="field-help">
      Incoming edge fields are still useful, but only as upstream recommendations. They are not the only legal source of pull keys.
    </div>

    <div class="object-card">
      <div class="row-head">Add Workflow Key</div>
      <label>
        <span>Key Name</span>
        <input
          v-model="newKeyName"
          placeholder="analysis_result"
        />
      </label>
      <label>
        <span>Description</span>
        <input
          v-model="newKeyDescription"
          placeholder="Structured result shared across the workflow"
        />
      </label>
      <button type="button" class="mini-button align-end" @click="addKey">Add Key</button>
    </div>

    <div v-if="sortedKeys.length" class="editor-rows">
      <div
        v-for="item in sortedKeys"
        :key="item.key"
        class="object-card"
      >
        <div class="row-head">{{ item.key }}</div>
        <div class="field-help">Sources: {{ item.sources.join(', ') || 'unknown' }}</div>
        <div class="field-help">Owners: {{ item.owners.join(', ') || 'workflow' }}</div>
        <label>
          <span>Description</span>
          <input
            :value="item.description"
            placeholder="Explain what this key carries"
            @input="updateDescription(item.key, $event.target.value)"
          />
        </label>
        <label>
          <span>Rename Key</span>
          <input
            :value="pendingNames[item.key] ?? item.key"
            placeholder="analysis_result"
            @input="pendingNames[item.key] = $event.target.value"
            @blur="commitRename(item.key)"
            @keydown.enter.prevent="commitRename(item.key)"
          />
        </label>
      </div>
    </div>
  </section>
</template>
