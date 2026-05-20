<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  value: { type: Array, default: () => [] },
  help: { type: String, default: '' },
  title: { type: String, default: 'Tools' },
  allowMcp: { type: Boolean, default: true }
});

const emit = defineEmits(['update:value']);

const rows = ref([]);
const lastSignature = ref('');
let rowCounter = 0;

const builtinOptions = [
  {
    value: 'echo',
    label: 'echo',
    help: 'Return input text unchanged.'
  },
  {
    value: 'json_inspect',
    label: 'json_inspect',
    help: 'Render a payload as formatted JSON.'
  },
  {
    value: 'list_keys',
    label: 'list_keys',
    help: 'Return top-level keys from an object payload.'
  },
  {
    value: 'concat_text',
    label: 'concat_text',
    help: 'Concatenate two text fragments.'
  }
];

const httpMethods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
const responseModes = ['json', 'text'];

function nextRowId() {
  rowCounter += 1;
  return `tool-row:${rowCounter}`;
}

function createDefaultTool() {
  return {
    name: '',
    binding: 'builtin',
    description: '',
    config: {
      method: 'POST',
      url: '',
      headers: {},
      params: {},
      body: {},
      response: 'json',
      timeout: 20
    }
  };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function normalizeConfig(rawConfig = {}) {
  return {
    method: String(rawConfig.method || 'POST').toUpperCase(),
    url: String(rawConfig.url || ''),
    headers: rawConfig.headers && typeof rawConfig.headers === 'object' ? clone(rawConfig.headers) : {},
    params: rawConfig.params && typeof rawConfig.params === 'object' ? clone(rawConfig.params) : {},
    body: rawConfig.body !== undefined ? clone(rawConfig.body) : {},
    response: String(rawConfig.response || 'json'),
    timeout: rawConfig.timeout !== undefined && rawConfig.timeout !== null && rawConfig.timeout !== '' ? Number(rawConfig.timeout) : 20
  };
}

function normalizeTool(raw) {
  const base = createDefaultTool();
  const item = {
    ...base,
    ...(raw || {}),
    config: normalizeConfig(raw?.config || {})
  };
  if (!item.binding) item.binding = 'builtin';
  return item;
}

function serialize(items) {
  return JSON.stringify(
    items.map((item) => ({
      name: String(item.name || ''),
      binding: String(item.binding || ''),
      description: String(item.description || ''),
      config: normalizeConfig(item.config || {})
    }))
  );
}

function syncRows(rawValue) {
  const normalized = (rawValue || []).map((item) => normalizeTool(item));
  rows.value = normalized.length
    ? normalized.map((item, index) => ({
        id: rows.value[index]?.id || nextRowId(),
        data: item
      }))
    : [
        {
          id: nextRowId(),
          data: createDefaultTool()
        }
      ];
}

watch(
  () => props.value,
  (nextValue) => {
    const signature = serialize((nextValue || []).map((item) => normalizeTool(item)));
    if (signature === lastSignature.value) return;
    syncRows(nextValue);
    lastSignature.value = signature;
  },
  { deep: true, immediate: true }
);

function commit() {
  const normalized = rows.value
    .map((row) => normalizeTool(row.data))
    .filter((item) => String(item.name || '').trim() || String(item.description || '').trim());
  lastSignature.value = serialize(normalized);
  emit('update:value', normalized);
}

function updateField(index, field, value) {
  rows.value[index] = {
    ...rows.value[index],
    data: {
      ...rows.value[index].data,
      [field]: value
    }
  };
  commit();
}

function updateConfigField(index, field, value) {
  const current = rows.value[index].data;
  rows.value[index] = {
    ...rows.value[index],
    data: {
      ...current,
      config: {
        ...normalizeConfig(current.config || {}),
        [field]: value
      }
    }
  };
  commit();
}

function parseJsonInput(raw, fallback) {
  const text = String(raw || '').trim();
  if (!text) return clone(fallback);
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === 'object' ? parsed : clone(fallback);
  } catch {
    return raw;
  }
}

function updateJsonConfigField(index, field, raw) {
  const current = rows.value[index].data;
  const fallback = field === 'body' ? {} : {};
  rows.value[index] = {
    ...rows.value[index],
    data: {
      ...current,
      config: {
        ...normalizeConfig(current.config || {}),
        [field]: parseJsonInput(raw, fallback)
      }
    }
  };
  commit();
}

function addTool(preset) {
  rows.value.push({
    id: nextRowId(),
    data: normalizeTool(preset || createDefaultTool())
  });
  commit();
}

function removeTool(index) {
  rows.value.splice(index, 1);
  if (!rows.value.length) {
    rows.value.push({
      id: nextRowId(),
      data: createDefaultTool()
    });
  }
  commit();
}

function selectBuiltin(index, builtinName) {
  const builtin = builtinOptions.find((item) => item.value === builtinName);
  updateField(index, 'name', builtinName);
  if (builtin && !String(rows.value[index].data.description || '').trim()) {
    updateField(index, 'description', builtin.help);
  }
}

function useBuiltinPreset(name) {
  const preset = builtinOptions.find((item) => item.value === name);
  addTool({
    name,
    binding: 'builtin',
    description: preset?.help || '',
    config: createDefaultTool().config
  });
}

function useApiPreset() {
  addTool({
    name: 'http_api',
    binding: 'api',
    description: 'Call an external HTTP endpoint.',
    config: {
      method: 'POST',
      url: 'https://example.com/endpoint',
      headers: {},
      params: {},
      body: { query: '{query}' },
      response: 'json',
      timeout: 20
    }
  });
}

const exampleBuiltin = computed(() => ({
  name: 'json_inspect',
  binding: 'builtin',
  description: 'Render payload as formatted JSON for inspection.'
}));
</script>

<template>
  <div class="structured-editor">
    <div class="section-title">{{ title }}</div>
    <div v-if="help" class="field-help">{{ help }}</div>

    <div class="suggestion-strip">
      <div class="suggestion-title">Quick Add</div>
      <div class="suggestion-list">
        <button type="button" class="suggestion-chip" @click="useBuiltinPreset('echo')">
          <span>Echo</span>
          <small>Return text unchanged</small>
        </button>
        <button type="button" class="suggestion-chip" @click="useBuiltinPreset('json_inspect')">
          <span>JSON Inspect</span>
          <small>Pretty-print payload</small>
        </button>
        <button type="button" class="suggestion-chip" @click="useBuiltinPreset('list_keys')">
          <span>List Keys</span>
          <small>Show top-level keys</small>
        </button>
        <button type="button" class="suggestion-chip" @click="useApiPreset()">
          <span>HTTP API</span>
          <small>Call external endpoint</small>
        </button>
      </div>
    </div>

    <div class="object-card">
      <div class="row-head">Simple builtin example</div>
      <pre>{{ JSON.stringify(exampleBuiltin, null, 2) }}</pre>
    </div>

    <div class="editor-rows">
      <div v-for="(row, index) in rows" :key="row.id" class="object-card">
        <div class="row-head">Tool {{ index + 1 }}</div>

        <label>
          <span>Binding</span>
          <select :value="row.data.binding" @change="updateField(index, 'binding', $event.target.value)">
            <option value="builtin">builtin</option>
            <option value="api">api</option>
            <option v-if="allowMcp" value="mcp">mcp</option>
            <option value="other">other</option>
          </select>
        </label>
        <div class="field-help">
          `builtin` means a local backend-provided tool. `api` means an HTTP tool configured below. `mcp` is still declaration-only.
        </div>

        <template v-if="row.data.binding === 'builtin'">
          <label>
            <span>Builtin Tool</span>
            <select :value="row.data.name" @change="selectBuiltin(index, $event.target.value)">
              <option value="">Select</option>
              <option v-for="item in builtinOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <div class="field-help">
            {{
              builtinOptions.find((item) => item.value === row.data.name)?.help ||
              'Choose one of the backend-supported builtin tools.'
            }}
          </div>
        </template>

        <template v-else>
          <label>
            <span>Name</span>
            <input
              :value="row.data.name || ''"
              placeholder="http_api / search_api / weather_api"
              @input="updateField(index, 'name', $event.target.value)"
            />
          </label>
        </template>

        <label>
          <span>Description</span>
          <textarea
            :value="row.data.description || ''"
            placeholder="Explain what this tool is for and when the agent should use it."
            @input="updateField(index, 'description', $event.target.value)"
          />
        </label>

        <template v-if="row.data.binding === 'api'">
          <div class="subsection-title">API Configuration</div>
          <label>
            <span>Method</span>
            <select :value="row.data.config.method" @change="updateConfigField(index, 'method', $event.target.value)">
              <option v-for="method in httpMethods" :key="method" :value="method">{{ method }}</option>
            </select>
          </label>
          <label>
            <span>URL</span>
            <input
              :value="row.data.config.url || ''"
              placeholder="https://example.com/endpoint"
              @input="updateConfigField(index, 'url', $event.target.value)"
            />
          </label>
          <label>
            <span>Response Mode</span>
            <select :value="row.data.config.response" @change="updateConfigField(index, 'response', $event.target.value)">
              <option v-for="mode in responseModes" :key="mode" :value="mode">{{ mode }}</option>
            </select>
          </label>
          <label>
            <span>Timeout (seconds)</span>
            <input
              type="number"
              min="1"
              step="1"
              :value="row.data.config.timeout"
              @input="updateConfigField(index, 'timeout', Number($event.target.value || 20))"
            />
          </label>
          <label>
            <span>Headers JSON</span>
            <textarea
              :value="JSON.stringify(row.data.config.headers || {}, null, 2)"
              placeholder='{"Authorization":"Bearer YOUR_KEY"}'
              @input="updateJsonConfigField(index, 'headers', $event.target.value)"
            />
          </label>
          <label>
            <span>Query Params JSON</span>
            <textarea
              :value="JSON.stringify(row.data.config.params || {}, null, 2)"
              placeholder='{"q":"{query}"}'
              @input="updateJsonConfigField(index, 'params', $event.target.value)"
            />
          </label>
          <label>
            <span>Body JSON</span>
            <textarea
              :value="JSON.stringify(row.data.config.body ?? {}, null, 2)"
              placeholder='{"query":"{query}"}'
              @input="updateJsonConfigField(index, 'body', $event.target.value)"
            />
          </label>
          <div class="field-help">
            You can use placeholders like <code>{query}</code> inside URL, headers, params, or body values.
          </div>
        </template>

        <template v-else-if="row.data.binding === 'mcp'">
          <div class="field-help">
            MCP tools are not runtime-bound yet in ClawCanvas. Use this only as metadata for export.
          </div>
        </template>

        <button type="button" class="mini-button ghost align-end" @click="removeTool(index)">Remove</button>
      </div>
    </div>

    <button type="button" class="mini-button" @click="addTool()">Add Tool</button>
  </div>
</template>
