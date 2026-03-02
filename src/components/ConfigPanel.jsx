import React, { useState, useCallback } from 'react';
import { X, Upload, FileText, Trash2, CheckCircle, Loader, AlertCircle } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

const BACKEND_URL = 'http://localhost:8000';

export default function ConfigPanel() {
  const nodes = useFlowStore((s) => s.nodes);
  const selectedNode = useFlowStore((s) => s.selectedNode);
  const updateNodeData = useFlowStore((s) => s.updateNodeData);
  const setSelectedNode = useFlowStore((s) => s.setSelectedNode);

  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);

  const node = nodes.find((n) => n.id === selectedNode);
  if (!node) return null;

  const { data } = node;
  const config = data.config || {};

  const updateConfig = (key, value) => {
    updateNodeData(node.id, {
      config: { ...config, [key]: value },
    });
  };

  // ── File upload handler for Knowledge Base ──
  const handleFileUpload = useCallback(async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadStatus(null);

    const kbId = config.kbId || `kb-${node.id}`;
    const currentFiles = config.files || [];
    let totalChunks = config.chunkCount || 0;

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('kb_id', kbId);

      try {
        const response = await fetch(`${BACKEND_URL}/api/kb/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          setUploadStatus({ type: 'error', message: err.detail || `Failed to upload ${file.name}` });
          continue;
        }

        const result = await response.json();
        currentFiles.push({
          name: result.filename,
          chunks: result.chunks,
          pages: result.pages,
        });
        totalChunks += result.chunks;

        setUploadStatus({
          type: 'success',
          message: `${result.filename}: ${result.chunks} chunks from ${result.pages} pages`,
        });
      } catch (err) {
        setUploadStatus({ type: 'error', message: `Upload error: ${err.message}` });
      }
    }

    // Update node config with kbId and files
    updateNodeData(node.id, {
      config: { ...config, kbId, files: currentFiles, chunkCount: totalChunks },
      label: currentFiles.length > 0
        ? `Knowledge Base (${currentFiles.length} files)`
        : 'Knowledge Base',
    });

    setUploading(false);
    // Reset file input
    e.target.value = '';
  }, [config, node.id, updateNodeData]);

  const handleRemoveFile = (fileIndex) => {
    const currentFiles = [...(config.files || [])];
    const removed = currentFiles.splice(fileIndex, 1);
    const newChunkCount = (config.chunkCount || 0) - (removed[0]?.chunks || 0);
    updateNodeData(node.id, {
      config: { ...config, files: currentFiles, chunkCount: Math.max(0, newChunkCount) },
      label: currentFiles.length > 0
        ? `Knowledge Base (${currentFiles.length} files)`
        : 'Knowledge Base',
    });
  };

  // ── Render sections ──

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

  const renderKBConfig = () => {
    const files = config.files || [];
    return (
      <>
        <div className="config-field">
          <label>Knowledge Base</label>
          <p className="config-help-text">
            Upload documents (PDF, TXT, CSV, MD) for your agent to search through using RAG.
          </p>
        </div>

        {/* Upload area */}
        <div className="kb-upload-area">
          <input
            type="file"
            id="kb-file-upload"
            multiple
            accept=".pdf,.txt,.csv,.md,.json,.py,.js,.html,.css"
            onChange={handleFileUpload}
            disabled={uploading}
            style={{ display: 'none' }}
          />
          <label htmlFor="kb-file-upload" className={`kb-upload-btn ${uploading ? 'disabled' : ''}`}>
            {uploading ? (
              <>
                <Loader size={16} className="step-spinner" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Upload size={16} />
                <span>Upload Files</span>
              </>
            )}
          </label>
        </div>

        {/* Upload status */}
        {uploadStatus && (
          <div className={`kb-status ${uploadStatus.type}`}>
            {uploadStatus.type === 'success' ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            <span>{uploadStatus.message}</span>
          </div>
        )}

        {/* File list */}
        {files.length > 0 && (
          <div className="kb-file-list">
            <label>Uploaded Files ({files.length})</label>
            {files.map((file, i) => (
              <div key={i} className="kb-file-item">
                <FileText size={14} />
                <div className="kb-file-info">
                  <span className="kb-file-name">{file.name}</span>
                  <span className="kb-file-meta">{file.chunks} chunks · {file.pages} pages</span>
                </div>
                <button className="kb-file-remove" onClick={() => handleRemoveFile(i)}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* KB stats */}
        {config.chunkCount > 0 && (
          <div className="kb-stats">
            <span>📊 Total: {config.chunkCount} chunks indexed</span>
            {config.kbId && <span className="kb-id">ID: {config.kbId}</span>}
          </div>
        )}
      </>
    );
  };

  const renderToolConfig = () => {
    // Special handling for Knowledge Base nodes
    if (data.toolId === 'tool-knowledge-base') {
      return renderKBConfig();
    }

    return (
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
  };

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
