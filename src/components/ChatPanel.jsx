import React, { useRef, useEffect, useState } from 'react';
import { X, Send, Brain, Wrench, CheckCircle, Loader, Search, Calculator, Code, Globe, BookOpen } from 'lucide-react';
import useFlowStore from '../store/useFlowStore';

const BACKEND_URL = 'http://localhost:8000';

const nodeIconMap = {
  llm: Brain,
  tool: Wrench,
  web_search: Search,
  calculator: Calculator,
  code_interpreter: Code,
  api_call: Globe,
  wikipedia_search: BookOpen,
};

export default function ChatPanel() {
  const chatOpen = useFlowStore((s) => s.chatOpen);
  const setChatOpen = useFlowStore((s) => s.setChatOpen);
  const exportFlow = useFlowStore((s) => s.exportFlow);
  const agentName = useFlowStore((s) => s.agentName);

  const [messages, setMessages] = useState([]);
  const [steps, setSteps] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [finalAnswer, setFinalAnswer] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, steps, finalAnswer]);

  if (!chatOpen) return null;

  const handleSend = async () => {
    const message = input.trim();
    if (!message || isStreaming) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: message }]);
    setIsStreaming(true);
    setSteps([]);
    setFinalAnswer('');

    let accumulatedAnswer = '';
    let currentSteps = [];

    try {
      const graphData = exportFlow();
      const history = messages.map((m) => ({ role: m.role, content: m.content }));

      const controller = new AbortController();
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, graph: graphData, history }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; // Buffer for incomplete SSE lines

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on double newline (SSE event boundary)
        const parts = buffer.split('\n\n');
        // Keep the last part as buffer (may be incomplete)
        buffer = parts.pop() || '';

        for (const part of parts) {
          const lines = part.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6).trim();
            if (data === '[DONE]') continue;

            let parsed;
            try {
              parsed = JSON.parse(data);
            } catch {
              continue;
            }

            if (parsed.type === 'step') {
              if (parsed.step === 'node_executing') {
                currentSteps = currentSteps.map((s) =>
                  s.type === 'node_executing' && s.status === 'active'
                    ? { ...s, status: 'done' }
                    : s
                );
                currentSteps = [
                  ...currentSteps,
                  {
                    type: 'node_executing',
                    nodeType: parsed.nodeType,
                    nodeName: parsed.nodeName,
                    detail: parsed.detail || '',
                    status: 'active',
                  },
                ];
                setSteps([...currentSteps]);
              } else if (parsed.step === 'tool_call') {
                currentSteps = [
                  ...currentSteps,
                  {
                    type: 'tool_call',
                    toolName: parsed.toolName,
                    nodeName: parsed.nodeName,
                    input: parsed.input,
                    status: 'active',
                  },
                ];
                setSteps([...currentSteps]);
              } else if (parsed.step === 'tool_result') {
                currentSteps = currentSteps.map((s) =>
                  s.type === 'tool_call' && s.status === 'active'
                    ? { ...s, status: 'done' }
                    : s
                );
                currentSteps = [
                  ...currentSteps,
                  { type: 'tool_result', nodeName: parsed.nodeName, content: parsed.content },
                ];
                setSteps([...currentSteps]);
              } else if (parsed.step === 'done') {
                currentSteps = currentSteps.map((s) => ({ ...s, status: 'done' }));
                setSteps([...currentSteps]);
              }
            } else if (parsed.type === 'token' && parsed.token) {
              currentSteps = currentSteps.map((s) =>
                s.status === 'active' ? { ...s, status: 'done' } : s
              );
              setSteps([...currentSteps]);
              accumulatedAnswer += parsed.token;
              setFinalAnswer(accumulatedAnswer);
            } else if (parsed.error) {
              accumulatedAnswer += `\n⚠️ ${parsed.error}`;
              setFinalAnswer(accumulatedAnswer);
            }
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        const lines = buffer.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === 'token' && parsed.token) {
              accumulatedAnswer += parsed.token;
            }
          } catch {}
        }
      }

      if (accumulatedAnswer) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: accumulatedAnswer, steps: currentSteps },
        ]);
      } else if (currentSteps.length > 0) {
        // If we got steps but no answer text, still show something
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Agent completed without generating text.', steps: currentSteps },
        ]);
      }
    } catch (err) {
      // Save any partial answer we collected before the error
      const errorMsg = accumulatedAnswer
        ? accumulatedAnswer + `\n\n⚠️ ${err.message}`
        : `⚠️ Error: ${err.message}`;
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: errorMsg, steps: currentSteps },
      ]);
    } finally {
      setIsStreaming(false);
      setSteps([]);
      setFinalAnswer('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getIcon = (step) => {
    if (step.nodeType === 'llm') return Brain;
    if (step.toolName) return nodeIconMap[step.toolName] || Wrench;
    return nodeIconMap[step.nodeType] || Wrench;
  };

  const renderStep = (step, idx) => {
    const Icon = getIcon(step);

    if (step.type === 'node_executing') {
      const isLLM = step.nodeType === 'llm';
      return (
        <div key={idx} className={`step-card ${isLLM ? 'step-llm-node' : 'step-tool-node'}`}>
          <div className="step-header">
            <Icon size={14} />
            <span>
              <strong>{step.nodeName}</strong>
              {step.detail && <span className="step-detail"> — {step.detail}</span>}
            </span>
            {step.status === 'active' ? (
              <Loader size={12} className="step-spinner" />
            ) : (
              <CheckCircle size={12} className="step-done-icon" />
            )}
          </div>
        </div>
      );
    }

    if (step.type === 'tool_call') {
      return (
        <div key={idx} className="step-card step-tool-call">
          <div className="step-header">
            <Icon size={14} />
            <span>
              <strong>{step.nodeName}</strong> → calling tool
            </span>
            {step.status === 'active' ? (
              <Loader size={12} className="step-spinner" />
            ) : (
              <CheckCircle size={12} className="step-done-icon" />
            )}
          </div>
          {step.input && (
            <div className="step-body">
              <code>{step.input}</code>
            </div>
          )}
        </div>
      );
    }

    if (step.type === 'tool_result') {
      return (
        <div key={idx} className="step-card step-tool-result">
          <div className="step-header">
            <CheckCircle size={14} />
            <span>
              <strong>{step.nodeName}</strong> returned result
            </span>
          </div>
          <div className="step-body step-result-content">{step.content}</div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="chat-overlay" onClick={(e) => e.target === e.currentTarget && setChatOpen(false)}>
      <div className="chat-panel">
        <div className="chat-panel-header">
          <div className="chat-panel-header-info">
            <span className="chat-dot" />
            <h3>{agentName}</h3>
            <span className="chat-model-tag">Groq</span>
          </div>
          <button className="config-panel-close" onClick={() => setChatOpen(false)}>
            <X size={16} />
          </button>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && !isStreaming && (
            <div className="chat-message system">Start a conversation with your agent...</div>
          )}

          {messages.map((msg, i) => (
            <React.Fragment key={i}>
              {msg.role === 'assistant' && msg.steps && msg.steps.length > 0 && (
                <div className="steps-container">
                  {msg.steps.map((step, idx) => renderStep(step, idx))}
                </div>
              )}
              <div className={`chat-message ${msg.role}`}>{msg.content}</div>
            </React.Fragment>
          ))}

          {/* Live streaming steps */}
          {isStreaming && steps.length > 0 && (
            <div className="steps-container live">
              {steps.map((step, idx) => renderStep(step, idx))}
            </div>
          )}

          {/* Live streaming final answer */}
          {isStreaming && finalAnswer && (
            <div className="chat-message assistant streaming">{finalAnswer}</div>
          )}

          {isStreaming && !finalAnswer && steps.length === 0 && (
            <div className="typing-indicator">
              <span />
              <span />
              <span />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask your agent something..."
            disabled={isStreaming}
          />
          <button className="chat-send-btn" onClick={handleSend} disabled={isStreaming || !input.trim()}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
