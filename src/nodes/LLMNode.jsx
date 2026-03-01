import React from 'react';
import { Handle, Position } from 'reactflow';
import { Brain, Sparkles, Zap, X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

const iconMap = { Brain, Sparkles, Zap };

export default function LLMNode({ id, data, selected }) {
  const deleteNode = useFlowStore((s) => s.deleteNode);
  const IconComponent = iconMap[data.icon] || Brain;

  return (
    <div className={`custom-node llm-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <button className="node-delete-btn" onClick={() => deleteNode(id)}>
        <X size={10} />
      </button>
      <div className="custom-node-header">
        <div className="custom-node-icon">
          <IconComponent size={16} />
        </div>
        <span className="custom-node-title">{data.label}</span>
      </div>
      <div className="custom-node-body">
        <span className="custom-node-badge">
          {data.model || 'LLM'}
        </span>
        <div className="custom-node-meta">
          🌡 Temp: {data.config?.temperature ?? 0.7}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
