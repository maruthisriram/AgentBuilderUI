import React from 'react';
import { X } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

export default function ConfigPanel() {
  const nodes = useFlowStore((s) => s.nodes);
  const selectedNode = useFlowStore((s) => s.selectedNode);
  const updateNodeData = useFlowStore((s) => s.updateNodeData);
  const setSelectedNode = useFlowStore((s) => s.setSelectedNode);

  const node = nodes.find((n) => n.id === selectedNode);
  if (!node) return null;

  const { data } = node;
  const config = data.config || {};

  const updateConfig = (key, value) => {
    updateNodeData(node.id, {
      config: { ...config, [key]: value },
    });
  };

  const renderLLMConfig = () => (
    <>
      <div className="config-field">
        <label>Model</label>
        <input type="text" value={data.model || ''} readOnly />
      </div>
      <div className="config-field">
        <label>Temperature</label>
        <div className="range-row">
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={config.temperature ?? 0.7}
            onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
          />
          <span className="range-value">{config.temperature ?? 0.7}</span>
        </div>
      </div>
      <div className="config-field">
        <label>Max Tokens</label>
        <input
          type="number"
          value={config.maxTokens ?? 1024}
          onChange={(e) => updateConfig('maxTokens', parseInt(e.target.value) || 1024)}
        />
      </div>
      <div className="config-field">
        <label>System Prompt</label>
        <textarea
          value={config.systemPrompt ?? ''}
          onChange={(e) => updateConfig('systemPrompt', e.target.value)}
          placeholder="You are a helpful assistant..."
        />
      </div>
    </>
  );

  const renderToolConfig = () => (
    <>
      <div className="config-field">
        <label>Tool</label>
        <input type="text" value={data.label} readOnly />
      </div>
      {config.maxResults !== undefined && (
        <div className="config-field">
          <label>Max Results</label>
          <input
            type="number"
            value={config.maxResults}
            onChange={(e) => updateConfig('maxResults', parseInt(e.target.value) || 5)}
          />
        </div>
      )}
      {config.url !== undefined && (
        <>
          <div className="config-field">
            <label>URL</label>
            <input
              type="text"
              value={config.url}
              onChange={(e) => updateConfig('url', e.target.value)}
              placeholder="https://api.example.com/..."
            />
          </div>
          <div className="config-field">
            <label>Method</label>
            <select
              value={config.method || 'GET'}
              onChange={(e) => updateConfig('method', e.target.value)}
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>
        </>
      )}
    </>
  );

  const renderFlowConfig = () => (
    <>
      <div className="config-field">
        <label>Label</label>
        <input
          type="text"
          value={config.label || ''}
          onChange={(e) => updateConfig('label', e.target.value)}
        />
      </div>
      {config.condition !== undefined && (
        <div className="config-field">
          <label>Condition</label>
          <textarea
            value={config.condition}
            onChange={(e) => updateConfig('condition', e.target.value)}
            placeholder="e.g. has_tools_needed == true"
          />
        </div>
      )}
    </>
  );

  return (
    <div className="config-panel">
      <div className="config-panel-header">
        <span className="config-panel-title">Configure: {data.label}</span>
        <button className="config-panel-close" onClick={() => setSelectedNode(null)}>
          <X size={16} />
        </button>
      </div>
      <div className="config-panel-body">
        {data.category === 'llm' && renderLLMConfig()}
        {data.category === 'tool' && renderToolConfig()}
        {data.category === 'flow' && renderFlowConfig()}
      </div>
    </div>
  );
}
