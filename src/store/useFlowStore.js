import { create } from 'zustand';
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
} from 'reactflow';
import { v4 as uuidv4 } from 'uuid';
import { getToolDef } from '../data/toolDefinitions';

const useFlowStore = create((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  agentName: 'My Agent',
  chatOpen: false,
  chatMessages: [],
  isStreaming: false,

  setAgentName: (name) => set({ agentName: name }),

  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),

  onEdgesChange: (changes) =>
    set({ edges: applyEdgeChanges(changes, get().edges) }),

  onConnect: (connection) =>
    set({
      edges: addEdge(
        {
          ...connection,
          id: `edge-${uuidv4()}`,
          type: 'animatedEdge',
          animated: true,
        },
        get().edges
      ),
    }),

  addNode: (toolId, position) => {
    const toolDef = getToolDef(toolId);
    if (!toolDef) return;

    const nodeId = `${toolDef.category}-${uuidv4().slice(0, 8)}`;
    
    let nodeType = 'toolNode';
    if (toolDef.category === 'llm') nodeType = 'llmNode';
    else if (toolDef.id === 'flow-input') nodeType = 'inputNode';
    else if (toolDef.id === 'flow-output') nodeType = 'outputNode';
    else if (toolDef.id === 'flow-conditional') nodeType = 'conditionalNode';

    const newNode = {
      id: nodeId,
      type: nodeType,
      position,
      data: {
        toolId: toolDef.id,
        label: toolDef.name,
        description: toolDef.description,
        icon: toolDef.icon,
        category: toolDef.category,
        model: toolDef.model || null,
        config: { ...toolDef.defaultConfig },
      },
    };

    set({ nodes: [...get().nodes, newNode] });
  },

  updateNodeData: (nodeId, newData) => {
    set({
      nodes: get().nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, ...newData } }
          : node
      ),
    });
  },

  deleteNode: (nodeId) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== nodeId),
      edges: get().edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId
      ),
      selectedNode: get().selectedNode === nodeId ? null : get().selectedNode,
    });
  },

  setSelectedNode: (nodeId) => set({ selectedNode: nodeId }),

  clearFlow: () =>
    set({ nodes: [], edges: [], selectedNode: null }),

  saveFlow: () => {
    const { nodes, edges, agentName } = get();
    const data = JSON.stringify({ nodes, edges, agentName }, null, 2);
    localStorage.setItem('agent-builder-flow', data);
    return data;
  },

  loadFlow: () => {
    const saved = localStorage.getItem('agent-builder-flow');
    if (saved) {
      const { nodes, edges, agentName } = JSON.parse(saved);
      set({ nodes, edges, agentName: agentName || 'My Agent', selectedNode: null });
      return true;
    }
    return false;
  },

  exportFlow: () => {
    const { nodes, edges, agentName } = get();
    return { agentName, nodes, edges };
  },

  // Chat 
  setChatOpen: (open) => set({ chatOpen: open }),

  addChatMessage: (role, content) =>
    set({ chatMessages: [...get().chatMessages, { role, content, id: uuidv4() }] }),

  clearChat: () => set({ chatMessages: [] }),

  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  updateLastAssistantMessage: (content) => {
    const messages = [...get().chatMessages];
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') {
        messages[i] = { ...messages[i], content };
        break;
      }
    }
    set({ chatMessages: messages });
  },
}));

export default useFlowStore;
