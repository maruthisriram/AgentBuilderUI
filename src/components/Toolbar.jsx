import React from 'react';
import { Save, Upload, Trash2, Download, MessageSquarePlus, Cpu } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

export default function Toolbar() {
  const agentName = useFlowStore((s) => s.agentName);
  const setAgentName = useFlowStore((s) => s.setAgentName);
  const saveFlow = useFlowStore((s) => s.saveFlow);
  const loadFlow = useFlowStore((s) => s.loadFlow);
  const clearFlow = useFlowStore((s) => s.clearFlow);
  const exportFlow = useFlowStore((s) => s.exportFlow);
  const setChatOpen = useFlowStore((s) => s.setChatOpen);
  const nodes = useFlowStore((s) => s.nodes);

  const handleSave = () => {
    saveFlow();
    // Brief visual feedback
    const btn = document.getElementById('save-btn');
    if (btn) {
      btn.textContent = '✓ Saved!';
      setTimeout(() => { btn.textContent = 'Save'; }, 1500);
    }
  };

  const handleLoad = () => {
    const loaded = loadFlow();
    if (!loaded) {
      alert('No saved agent found.');
    }
  };

  const handleExport = () => {
    const data = exportFlow();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${agentName.replace(/\s+/g, '_').toLowerCase()}_agent.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = () => {
    if (nodes.length === 0 || window.confirm('Clear all nodes and edges?')) {
      clearFlow();
    }
  };

  return (
    <div className="toolbar">
      <div className="toolbar-logo">
        <div className="toolbar-logo-icon">
          <Cpu size={18} />
        </div>
        <span>Agent Builder</span>
      </div>

      <div className="toolbar-agent-name">
        <input
          type="text"
          value={agentName}
          onChange={(e) => setAgentName(e.target.value)}
          placeholder="Agent Name..."
        />
      </div>

      <div className="toolbar-actions">
        <button className="toolbar-btn" onClick={handleSave} id="save-btn">
          <Save size={14} /> Save
        </button>
        <button className="toolbar-btn" onClick={handleLoad}>
          <Upload size={14} /> Load
        </button>
        <button className="toolbar-btn" onClick={handleExport}>
          <Download size={14} /> Export
        </button>
        <button className="toolbar-btn danger" onClick={handleClear}>
          <Trash2 size={14} /> Clear
        </button>
        <button className="toolbar-btn chat-btn" onClick={() => setChatOpen(true)}>
          <MessageSquarePlus size={14} /> Chat with Agent
        </button>
      </div>
    </div>
  );
}
