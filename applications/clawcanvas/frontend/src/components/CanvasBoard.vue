<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  nodes: { type: Array, required: true },
  edges: { type: Array, required: true },
  selectedNodeId: { type: String, default: '' }
});

const emit = defineEmits(['select-node', 'move-node', 'create-edge', 'status']);

const boardRef = ref(null);
let dragState = null;
let connectState = null;

const nodesById = computed(() => {
  const map = new Map();
  for (const node of props.nodes) {
    map.set(node.id, node);
  }
  return map;
});

const renderedEdges = computed(() => {
  return props.edges
    .map((edge) => {
      const source = nodesById.value.get(edge.source);
      const target = nodesById.value.get(edge.target);
      if (!source || !target) return null;
      return {
        ...edge,
        x1: source.position.x + 180,
        y1: source.position.y + 34,
        x2: target.position.x,
        y2: target.position.y + 34
      };
    })
    .filter(Boolean);
});

const previewEdge = computed(() => {
  if (!connectState) return null;
  const source = nodesById.value.get(connectState.sourceId);
  if (!source) return null;
  return {
    x1: source.position.x + 180,
    y1: source.position.y + 34,
    x2: connectState.pointerX,
    y2: connectState.pointerY
  };
});

function canAcceptInput(node) {
  return node.type !== 'start';
}

function canEmitOutput(node) {
  return node.type !== 'end';
}

function onNodeMouseDown(event, node) {
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

function startConnect(event, node) {
  if (!canEmitOutput(node)) return;
  emit('select-node', node.id);
  const point = toBoardPoint(event.clientX, event.clientY);
  connectState = {
    sourceId: node.id,
    pointerX: point.x,
    pointerY: point.y
  };
  emit('status', `Connecting from ${node.id}. Release on a target input handle.`);
  window.addEventListener('mousemove', onWindowMouseMove);
  window.addEventListener('mouseup', onWindowMouseUp);
}

function onInputHandleMouseUp(node) {
  if (!connectState || !canAcceptInput(node)) return;
  if (connectState.sourceId === node.id) {
    emit('status', 'Source and target cannot be the same node.');
    clearPointerState();
    return;
  }
  emit('create-edge', { source: connectState.sourceId, target: node.id });
  clearPointerState();
}

function onWindowMouseMove(event) {
  if (dragState) {
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    emit('move-node', {
      id: dragState.nodeId,
      position: {
        x: Math.max(12, dragState.originX + dx),
        y: Math.max(12, dragState.originY + dy)
      }
    });
  }

  if (connectState) {
    const point = toBoardPoint(event.clientX, event.clientY);
    connectState = {
      ...connectState,
      pointerX: point.x,
      pointerY: point.y
    };
  }
}

function onWindowMouseUp() {
  clearPointerState();
}

function clearPointerState() {
  dragState = null;
  connectState = null;
  window.removeEventListener('mousemove', onWindowMouseMove);
  window.removeEventListener('mouseup', onWindowMouseUp);
}

function toBoardPoint(clientX, clientY) {
  const rect = boardRef.value?.getBoundingClientRect();
  if (!rect) return { x: clientX, y: clientY };
  return {
    x: clientX - rect.left,
    y: clientY - rect.top
  };
}

function onBoardClick(event) {
  if (event.target === boardRef.value) {
    emit('select-node', '');
  }
}
</script>

<template>
  <div ref="boardRef" class="canvas-board" @click="onBoardClick">
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
        marker-end="url(#arrow)"
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
      :class="[`type-${node.type}`, { selected: node.id === selectedNodeId }]"
      :style="{ left: `${node.position.x}px`, top: `${node.position.y}px` }"
      @mousedown.stop="onNodeMouseDown($event, node)"
    >
      <button
        v-if="canAcceptInput(node)"
        type="button"
        class="node-handle input-handle"
        @mouseup.stop="onInputHandleMouseUp(node)"
      />
      <button
        v-if="canEmitOutput(node)"
        type="button"
        class="node-handle output-handle"
        @mousedown.stop.prevent="startConnect($event, node)"
      />
      <div class="node-type">{{ node.type }}</div>
      <div class="node-label">{{ node.label }}</div>
      <div class="node-id">{{ node.id }}</div>
    </div>
  </div>
</template>
