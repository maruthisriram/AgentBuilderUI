import React, { useCallback, useRef } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';

import useFlowStore from './store/useFlowStore';
import { nodeTypes } from './nodes/nodeTypes';
import { edgeTypes } from './edges/edgeTypes';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import ConfigPanel from './components/ConfigPanel';
import ChatPanel from './components/ChatPanel';

function Flow() {
  const reactFlowWrapper = useRef(null);
  const nodes = useFlowStore((s) => s.nodes);
  const edges = useFlowStore((s) => s.edges);
  const onNodesChange = useFlowStore((s) => s.onNodesChange);
  const onEdgesChange = useFlowStore((s) => s.onEdgesChange);
  const onConnect = useFlowStore((s) => s.onConnect);
  const addNode = useFlowStore((s) => s.addNode);
  const setSelectedNode = useFlowStore((s) => s.setSelectedNode);
  const selectedNode = useFlowStore((s) => s.selectedNode);

  const onDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();

      const toolId = e.dataTransfer.getData('application/agentbuilder');
      if (!toolId) return;

      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = {
        x: e.clientX - bounds.left - 100,
        y: e.clientY - bounds.top - 40,
      };

      addNode(toolId, position);
    },
    [addNode]
  );

  const onNodeClick = useCallback(
    (_, node) => {
      setSelectedNode(node.id);
    },
    [setSelectedNode]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, [setSelectedNode]);

  return (
    <div className="app-container">
      <Toolbar />
      <div className="main-content">
        <Sidebar />
        <div
          className="canvas-wrapper"
          ref={reactFlowWrapper}
          onDragOver={onDragOver}
          onDrop={onDrop}
        >
          {nodes.length === 0 && (
            <div className="empty-canvas">
              <h2>🤖 Build Your Agent</h2>
              <p>Drag nodes from the palette to get started</p>
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            deleteKeyCode="Delete"
            proOptions={{ hideAttribution: true }}
          >
            <Background color="rgba(255,255,255,0.03)" gap={20} size={1} />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                switch (node.type) {
                  case 'llmNode': return '#8b5cf6';
                  case 'toolNode': return '#06b6d4';
                  case 'inputNode': return '#10b981';
                  case 'outputNode': return '#f59e0b';
                  case 'conditionalNode': return '#ec4899';
                  default: return '#64748b';
                }
              }}
              maskColor="rgba(0,0,0,0.7)"
              style={{ backgroundColor: '#111827' }}
            />
          </ReactFlow>
        </div>
        {selectedNode && <ConfigPanel />}
      </div>
      <ChatPanel />
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <Flow />
    </ReactFlowProvider>
  );
}
