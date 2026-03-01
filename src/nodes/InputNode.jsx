import React from 'react';
import { Handle, Position } from 'reactflow';
import { MessageSquare, X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

export default function InputNode({ id, data, selected }) {
  const deleteNode = useFlowStore((s) => s.deleteNode);

  return (
    <div className={`custom-node input-node ${selected ? 'selected' : ''}`}>
      <button className="node-delete-btn" onClick={() => deleteNode(id)}>
        <X size={10} />
      </button>
      <div className="custom-node-header">
        <div className="custom-node-icon">
          <MessageSquare size={16} />
        </div>
        <span className="custom-node-title">{data.config?.label || 'User Input'}</span>
      </div>
      <div className="custom-node-body">
        <div className="custom-node-meta">Agent entry point</div>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
