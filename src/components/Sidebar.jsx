import React from 'react';
import {
  Brain, Sparkles, Zap, Search, Calculator, Code, Globe,
  BookOpen, MessageSquare, MessageCircle, GitBranch
} from 'lucide-react';
import { toolDefinitions } from '../data/toolDefinitions';

const iconMap = {
  Brain, Sparkles, Zap, Search, Calculator, Code, Globe,
  BookOpen, MessageSquare, MessageCircle, GitBranch,
};

const categories = [
  { key: 'llm', label: 'LLM Models', colorClass: 'llm' },
  { key: 'tool', label: 'Tools', colorClass: 'tool' },
  { key: 'flow', label: 'Flow Control', colorClass: 'flow' },
];

export default function Sidebar() {
  const onDragStart = (e, toolId) => {
    e.dataTransfer.setData('application/agentbuilder', toolId);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">Node Palette</div>
      {categories.map((cat) => {
        const items = toolDefinitions.filter((t) => t.category === cat.key);
        return (
          <div key={cat.key} className="sidebar-category">
            <div className="sidebar-category-title">
              <span>{cat.label}</span>
            </div>
            {items.map((tool) => {
              const IconComponent = iconMap[tool.icon] || Globe;
              return (
                <div
                  key={tool.id}
                  className="sidebar-item"
                  draggable
                  onDragStart={(e) => onDragStart(e, tool.id)}
                >
                  <div className={`sidebar-item-icon ${cat.colorClass}`}>
                    <IconComponent size={16} />
                  </div>
                  <div className="sidebar-item-info">
                    <div className="sidebar-item-name">{tool.name}</div>
                    <div className="sidebar-item-desc">{tool.description}</div>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
