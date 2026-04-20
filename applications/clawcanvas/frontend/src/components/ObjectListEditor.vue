<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  value: { type: Array, default: () => [] },
  fields: { type: Array, required: true },
  createItem: { type: Function, required: true },
  help: { type: String, default: '' },
  presets: { type: Array, default: () => [] },
  presetTitle: { type: String, default: 'Starter Entries' }
});

const emit = defineEmits(['update:value']);

const rows = ref([]);
const lastEmittedSignature = ref('');
let rowCounter = 0;

function nextRowId() {
  rowCounter += 1;
  return `row:${rowCounter}`;
}

function defaultItem() {
  return { ...props.createItem() };
}

function normalizeItem(raw) {
  return {
    ...defaultItem(),
    ...(raw || {})
  };
}

function normalizeValue(raw) {
  return (raw || []).map((item) => normalizeItem(item));
}

function isEmptyItem(item) {
  return !props.fields.some((field) => String(item[field.key] || '').trim());
}

function serializeValue(items) {
  return JSON.stringify(
    items.map((item) => {
      const normalized = {};
      for (const field of props.fields) {
        normalized[field.key] = String(item[field.key] ?? '');
      }
      return normalized;
    })
  );
}

function syncRows(raw) {
  const normalized = normalizeValue(raw);
  const nextRows = normalized.map((item, index) => ({
    id: rows.value[index]?.id || nextRowId(),
    data: item
  }));
  const draftRows = rows.value
    .slice(normalized.length)
    .filter((row) => isEmptyItem(row.data))
    .map((row) => ({ id: row.id, data: { ...row.data } }));
  rows.value = [...nextRows, ...draftRows];
  if (!rows.value.length) {
    rows.value = [{ id: nextRowId(), data: defaultItem() }];
  }
}

watch(
  () => props.value,
  (nextValue) => {
    const signature = serializeValue(normalizeValue(nextValue));
    if (signature === lastEmittedSignature.value) return;
    syncRows(nextValue);
    lastEmittedSignature.value = signature;
  },
  { deep: true, immediate: true }
);

function commit() {
  const normalized = rows.value
    .map((row) => normalizeItem(row.data))
    .filter((row) => !isEmptyItem(row));
  lastEmittedSignature.value = serializeValue(normalized);
  emit('update:value', normalized);
}

function updateCell(index, key, value) {
  rows.value[index] = {
    ...rows.value[index],
    data: {
      ...rows.value[index].data,
      [key]: value
    }
  };
  commit();
}

function addRow() {
  rows.value.push({
    id: nextRowId(),
    data: defaultItem()
  });
}

function removeRow(index) {
  rows.value.splice(index, 1);
  if (!rows.value.length) {
    rows.value.push({
      id: nextRowId(),
      data: defaultItem()
    });
  }
  commit();
}

function addPreset(item) {
  rows.value.push({
    id: nextRowId(),
    data: normalizeItem(item)
  });
  commit();
}
</script>

<template>
  <div class="structured-editor">
    <div v-if="help" class="field-help">{{ help }}</div>
    <div v-if="presets.length" class="suggestion-strip">
      <div class="suggestion-title">{{ presetTitle }}</div>
      <div class="suggestion-list">
        <button
          v-for="preset in presets"
          :key="preset.label"
          type="button"
          class="suggestion-chip"
          @click="addPreset(preset.item)"
        >
          <span>{{ preset.label }}</span>
          <small v-if="preset.description">{{ preset.description }}</small>
        </button>
      </div>
    </div>
    <div class="editor-rows">
      <div
        v-for="(row, index) in rows"
        :key="row.id"
        class="object-card"
      >
        <label v-for="field in fields" :key="field.key">
          <span>{{ field.label }}</span>
          <div v-if="field.help" class="field-help">{{ field.help }}</div>
          <select
            v-if="field.options"
            :value="row.data[field.key] || ''"
            @change="updateCell(index, field.key, $event.target.value)"
          >
            <option value="">Select</option>
            <option v-for="option in field.options" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <textarea
            v-else-if="field.multiline"
            :value="row.data[field.key] || ''"
            :placeholder="field.placeholder || ''"
            @input="updateCell(index, field.key, $event.target.value)"
          />
          <input
            v-else
            :value="row.data[field.key] || ''"
            :placeholder="field.placeholder || ''"
            @input="updateCell(index, field.key, $event.target.value)"
          />
        </label>
        <button type="button" class="mini-button ghost align-end" @click="removeRow(index)">Remove</button>
      </div>
    </div>
    <button type="button" class="mini-button" @click="addRow">Add Item</button>
  </div>
</template>
