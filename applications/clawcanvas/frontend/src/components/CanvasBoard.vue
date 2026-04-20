<script setup>
import { computed, nextTick, ref } from 'vue';

const NODE_WIDTH = 180;
const NODE_HEIGHT = 68;
const WORLD_EXTENT = 100000;
const WORLD_ORIGIN = WORLD_EXTENT;

const props = defineProps({
  nodes: { type: Array, required: true },
  edges: { type: Array, required: true },
  selectedNodeId: { type: String, default: '' },
  selectedEdgeId: { type: String, default: '' }
});

const emit = defineEmits([
  'select-node',
  'select-edge',
  'move-node',
  'create-edge',
  'rename-node',
  'status'
]);

const viewportRef = ref(null);
const boardRef = ref(null);
const labelInputRef = ref(null);

const pan = ref({ x: 64 - WORLD_ORIGIN, y: 64 - WORLD_ORIGIN });
const pointerWorld = ref({ x: 0, y: 0 });
const renameDraft = ref('');
const editingNodeId = ref('');

let dragState = null;
let panState = null;
let pendingConnection = null;

const nodesById = computed(() => {
  const map = new Map();
  for (const node of props.nodes) {
    map.set(node.id, node);
  }
  return map;
});

const worldBounds = {
  width: WORLD_EXTENT * 2,
  height: WORLD_EXTENT * 2
};

function boardX(x) {
  return x + WORLD_ORIGIN;
}

function boardY(y) {
  return y + WORLD_ORIGIN;
}

const renderedEdges = computed(() => {
  return props.edges
    .map((edge) => {
      const source = nodesById.value.get(edge.source);
      const target = nodesById.value.get(edge.target);
      if (!source || !target) return null;
      return {
        ...edge,
        x1: boardX(source.position.x + NODE_WIDTH),
        y1: boardY(source.position.y + 34),
        x2: boardX(target.position.x),
        y2: boardY(target.position.y + 34)
      };
    })
    .filter(Boolean);
});

const previewEdge = computed(() => {
  if (!pendingConnection) return null;
  const source = nodesById.value.get(pendingConnection.nodeId);
  if (!source) return null;
  const startX =
    pendingConnection.side === 'right'
      ? boardX(source.position.x + NODE_WIDTH)
      : boardX(source.position.x);
  const startY = boardY(source.position.y + 34);
  return {
    x1: startX,
    y1: startY,
    x2: pointerWorld.value.x,
    y2: pointerWorld.value.y
  };
});

function nodeHandleRole(node, side) {
  if (side === 'left') {
    return node.type === 'start' ? 'disabled' : 'input';
  }
  return node.type === 'end' ? 'disabled' : 'output';
}

function onNodeMouseDown(event, node) {
  if (editingNodeId.value) return;
  emit('select-node', node.id);
  dragState = {
    nodeId: node.id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.position.x,
    originY: node.position.y
  };
  window.addEventListener('mousemove', onWindowMouseMove);
  window.addEventListener('mouseup', onWindowMouseUp);
}

function onViewportMouseDown(event) {
  const isCanvasBackground =
    event.target === viewportRef.value ||
    event.target === boardRef.value ||
    event.target?.classList?.contains?.('canvas-lines');
  if (!isCanvasBackground) return;
  panState = {
    startX: event.clientX,
    startY: event.clientY,
    originX: pan.value.x,
    originY: pan.value.y
  };
  emit('select-node', '');
  window.addEventListener('mousemove', onWindowMouseMove);
  window.addEventListener('mouseup', onWindowMouseUp);
}

function onWindowMouseMove(event) {
  updatePointerWorld(event.clientX, event.clientY);

  if (dragState) {
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    emit('move-node', {
      id: dragState.nodeId,
      position: {
        x: dragState.originX + dx,
        y: dragState.originY + dy
      }
    });
  }

  if (panState) {
    const dx = event.clientX - panState.startX;
    const dy = event.clientY - panState.startY;
    pan.value = {
      x: panState.originX + dx,
      y: panState.originY + dy
    };
  }
}

function onWindowMouseUp() {
  dragState = null;
  panState = null;
  window.removeEventListener('mousemove', onWindowMouseMove);
  window.removeEventListener('mouseup', onWindowMouseUp);
}

function onViewportMouseMove(event) {
  updatePointerWorld(event.clientX, event.clientY);
}

function updatePointerWorld(clientX, clientY) {
  const rect = viewportRef.value?.getBoundingClientRect();
  if (!rect) return;
  pointerWorld.value = {
    x: clientX - rect.left - pan.value.x,
    y: clientY - rect.top - pan.value.y
  };
}

function clickHandle(node, side) {
  if (editingNodeId.value) return;
  const role = nodeHandleRole(node, side);
  if (role === 'disabled') return;

  emit('select-node', node.id);

  if (!pendingConnection) {
    pendingConnection = { nodeId: node.id, side, role };
    pointerWorld.value = {
      x: side === 'right' ? boardX(node.position.x + NODE_WIDTH) : boardX(node.position.x),
      y: boardY(node.position.y + 34)
    };
    emit('status', `Selected ${node.id} ${side} handle. Click another compatible handle to create an edge.`);
    return;
  }

  const first = pendingConnection;
  if (first.nodeId === node.id && first.side === side) {
    pendingConnection = null;
    emit('status', 'Connection cancelled.');
    return;
  }

  if (first.role === role) {
    pendingConnection = { nodeId: node.id, side, role };
    emit('status', `Re-selected ${node.id} ${side} handle. Now click a compatible handle.`);
    return;
  }

  const source = first.role === 'output' ? first : { nodeId: node.id, side, role };
  const target = first.role === 'input' ? first : { nodeId: node.id, side, role };

  if (source.nodeId === target.nodeId) {
    emit('status', 'Source and target cannot be the same node.');
    pendingConnection = null;
    return;
  }

  emit('create-edge', { source: source.nodeId, target: target.nodeId });
  pendingConnection = null;
}

function onViewportClick(event) {
  const isCanvasBackground =
    event.target === viewportRef.value ||
    event.target === boardRef.value ||
    event.target?.classList?.contains?.('canvas-lines');
  if (isCanvasBackground) {
    if (pendingConnection) {
      pendingConnection = null;
      emit('status', 'Connection cancelled.');
    }
    emit('select-node', '');
    emit('select-edge', '');
  }
}

function selectEdge(edgeId) {
  if (editingNodeId.value) return;
  emit('select-edge', edgeId);
}

function beginRename(node) {
  emit('select-node', node.id);
  editingNodeId.value = node.id;
  renameDraft.value = node.label;
  nextTick(() => {
    labelInputRef.value?.focus();
    labelInputRef.value?.select();
  });
}

function commitRename() {
  if (!editingNodeId.value) return;
  const trimmed = renameDraft.value.trim();
  if (trimmed) {
    emit('rename-node', { id: editingNodeId.value, label: trimmed });
  }
  editingNodeId.value = '';
  renameDraft.value = '';
}

function cancelRename() {
  editingNodeId.value = '';
  renameDraft.value = '';
}
</script>

<template>
  <div
    ref="viewportRef"
    class="canvas-viewport"
    @mousedown="onViewportMouseDown"
    @mousemove="onViewportMouseMove"
    @click="onViewportClick"
  >
    <div
      ref="boardRef"
      class="canvas-board"
      :style="{
        width: `${worldBounds.width}px`,
        height: `${worldBounds.height}px`,
        transform: `translate(${pan.x}px, ${pan.y}px)`
      }"
    >
      <svg class="canvas-lines" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker
            id="arrow"
            markerWidth="12"
            markerHeight="12"
            refX="10"
            refY="6"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M 0 0 L 12 6 L 0 12 z" fill="#29425f" />
          </marker>
        </defs>
        <line
          v-for="edge in renderedEdges"
          :key="edge.id"
          :x1="edge.x1"
          :y1="edge.y1"
          :x2="edge.x2"
          :y2="edge.y2"
          class="edge-line"
          :class="{ selected: edge.id === selectedEdgeId }"
          marker-end="url(#arrow)"
          @mousedown.stop
          @click.stop="selectEdge(edge.id)"
        />
        <line
          v-if="previewEdge"
          :x1="previewEdge.x1"
          :y1="previewEdge.y1"
          :x2="previewEdge.x2"
          :y2="previewEdge.y2"
          class="edge-line preview"
          marker-end="url(#arrow)"
        />
      </svg>

      <div
        v-for="node in nodes"
        :key="node.id"
        class="canvas-node"
        :class="[
          `type-${node.type}`,
          { selected: node.id === selectedNodeId, renaming: editingNodeId === node.id }
        ]"
        :style="{ left: `${boardX(node.position.x)}px`, top: `${boardY(node.position.y)}px` }"
        @mousedown.stop="onNodeMouseDown($event, node)"
      >
        <button
          type="button"
          class="node-handle input-handle"
          :class="{ disabled: nodeHandleRole(node, 'left') === 'disabled' }"
          @click.stop="clickHandle(node, 'left')"
        />
        <button
          type="button"
          class="node-handle output-handle"
          :class="{ disabled: nodeHandleRole(node, 'right') === 'disabled' }"
          @click.stop="clickHandle(node, 'right')"
        />
        <div class="node-type">{{ node.type }}</div>
        <div v-if="editingNodeId !== node.id" class="node-label" @dblclick.stop="beginRename(node)">
          {{ node.label }}
        </div>
        <input
          v-else
          ref="labelInputRef"
          v-model="renameDraft"
          class="node-label-input"
          @mousedown.stop
          @click.stop
          @keydown.enter.prevent="commitRename"
          @keydown.esc.prevent="cancelRename"
          @blur="commitRename"
        />
        <div class="node-id">{{ node.id }}</div>
      </div>
    </div>
  </div>
</template>
