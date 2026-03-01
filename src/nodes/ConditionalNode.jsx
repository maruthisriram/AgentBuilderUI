import React from 'react';
import { Handle, Position } from 'reactflow';
import { GitBranch, X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

export default function ConditionalNode({ id, data, selected }) {
  const deleteNode = useFlowStore((s) => s.deleteNode);

  return (
    <div className={`custom-node conditional-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <button className="node-delete-btn" onClick={() => deleteNode(id)}>
        <X size={10} />
      </button>
      <div className="custom-node-header">
        <div className="custom-node-icon">
          <GitBranch size={16} />
        </div>
        <span className="custom-node-title">Conditional Router</span>
      </div>
      <div className="custom-node-body">
        <div className="custom-node-meta">
          {data.config?.condition || 'Set condition...'}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: '30%' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: '70%' }}
      />
    </div>
  );
}
