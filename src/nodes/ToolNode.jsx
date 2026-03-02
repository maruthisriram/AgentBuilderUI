import React from 'react';
import { Handle, Position } from 'reactflow';
import { Search, Calculator, Code, Globe, BookOpen, FileUp, X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

const iconMap = { Search, Calculator, Code, Globe, BookOpen, FileUp };

export default function ToolNode({ id, data, selected }) {
  const deleteNode = useFlowStore((s) => s.deleteNode);
  const IconComponent = iconMap[data.icon] || Globe;

  return (
    <div className={`custom-node tool-node ${selected ? 'selected' : ''}`}>
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
        <span className="custom-node-badge">{data.description}</span>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
