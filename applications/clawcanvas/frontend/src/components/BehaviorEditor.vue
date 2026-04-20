<script setup>
import StringListEditor from './StringListEditor.vue';

const props = defineProps({
  value: { type: Object, default: () => ({ style: '', rules: [] }) },
  styleLabel: { type: String, default: 'Style' },
  help: { type: String, default: '' },
  styleSuggestions: { type: Array, default: () => [] },
  ruleSuggestions: { type: Array, default: () => [] }
});

const emit = defineEmits(['update:value']);

function updateField(field, value) {
  emit('update:value', {
    style: props.value?.style || '',
    rules: props.value?.rules || [],
    ...props.value,
    [field]: value
  });
}
</script>

<template>
  <div class="structured-editor">
    <div v-if="help" class="field-help">{{ help }}</div>
    <label>
      <span>{{ styleLabel }}</span>
      <input
        :value="value?.style || ''"
        placeholder="structured / concise / formal ..."
        @input="updateField('style', $event.target.value)"
      />
    </label>
    <div v-if="styleSuggestions.length" class="suggestion-strip">
      <div class="suggestion-title">Suggested Styles</div>
      <div class="suggestion-list">
        <button
          v-for="styleItem in styleSuggestions"
          :key="styleItem"
          type="button"
          class="suggestion-chip"
          @click="updateField('style', styleItem)"
        >
          <span>{{ styleItem }}</span>
        </button>
      </div>
    </div>
    <StringListEditor
      :value="value?.rules || []"
      placeholder="Add one rule"
      help="Rules are checked line by line. Each item should be one concrete instruction."
      :suggestions="ruleSuggestions"
      suggestion-title="Suggested Rules"
      @update:value="updateField('rules', $event)"
    />
  </div>
</template>
