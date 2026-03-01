import React from 'react';
import { Handle, Position } from 'reactflow';
import { MessageCircle, X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

export default function OutputNode({ id, data, selected }) {
  const deleteNode = useFlowStore((s) => s.deleteNode);

  return (
    <div className={`custom-node output-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <button className="node-delete-btn" onClick={() => deleteNode(id)}>
        <X size={10} />
      </button>
      <div className="custom-node-header">
        <div className="custom-node-icon">
          <MessageCircle size={16} />
        </div>
        <span className="custom-node-title">{data.config?.label || 'Agent Output'}</span>
      </div>
      <div className="custom-node-body">
        <div className="custom-node-meta">Final response</div>
      </div>
    </div>
  );
}
