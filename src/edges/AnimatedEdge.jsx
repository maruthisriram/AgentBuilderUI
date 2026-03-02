import React, { useMemo } from 'react';
import { getBezierPath, EdgeLabelRenderer } from 'reactflow';
import useFlowStore from '../store/useFlowStore';

/**
 * Determine the data-flow label for an edge based on source and target node types.
 */
function getEdgeLabel(sourceNode, targetNode) {
  if (!sourceNode || !targetNode) return '';

  const srcCat = sourceNode.data?.category;
  const tgtCat = targetNode.data?.category;
  const srcToolId = sourceNode.data?.toolId;
  const tgtToolId = targetNode.data?.toolId;

  // Input → LLM
  if (srcToolId === 'flow-input' && tgtCat === 'llm') return 'user query';
  // LLM → Output
  if (srcCat === 'llm' && tgtToolId === 'flow-output') return 'response';
  // LLM → Tool
  if (srcCat === 'llm' && tgtCat === 'tool') return 'tool call';
  // LLM → LLM
  if (srcCat === 'llm' && tgtCat === 'llm') return 'handoff';
  // LLM → Conditional
  if (srcCat === 'llm' && tgtToolId === 'flow-conditional') return 'evaluate';
  // Conditional → LLM
  if (srcToolId === 'flow-conditional' && tgtCat === 'llm') return 'route';
  // Conditional → Output
  if (srcToolId === 'flow-conditional' && tgtToolId === 'flow-output') return 'route';

  return 'data';
}

/**
 * Color mapping for edge labels based on the flow type.
 */
function getLabelColor(label) {
  switch (label) {
    case 'user query': return { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', glow: '#10b981' };
    case 'response':   return { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', glow: '#f59e0b' };
    case 'tool call':  return { bg: 'rgba(6, 182, 212, 0.15)',   text: '#06b6d4', glow: '#06b6d4' };
    case 'handoff':    return { bg: 'rgba(168, 85, 247, 0.15)',  text: '#a855f7', glow: '#a855f7' };
    case 'evaluate':   return { bg: 'rgba(236, 72, 153, 0.15)',  text: '#ec4899', glow: '#ec4899' };
    case 'route':      return { bg: 'rgba(236, 72, 153, 0.15)',  text: '#ec4899', glow: '#ec4899' };
    default:           return { bg: 'rgba(100, 116, 139, 0.15)', text: '#94a3b8', glow: '#64748b' };
  }
}

export default function AnimatedEdge({
  id,
  source,
  target,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  sourceHandleId,
  style = {},
  markerEnd,
}) {
  const nodes = useFlowStore((s) => s.nodes);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const { label, colors } = useMemo(() => {
    const sourceNode = nodes.find((n) => n.id === source);
    const targetNode = nodes.find((n) => n.id === target);
    let edgeLabel = getEdgeLabel(sourceNode, targetNode);

    // For conditional edges, show the handle (true/false)
    if (sourceHandleId === 'true' || sourceHandleId === 'false') {
      edgeLabel = sourceHandleId === 'true' ? '✓ yes' : '✗ no';
    }

    return { label: edgeLabel, colors: getLabelColor(edgeLabel) };
  }, [nodes, source, target, sourceHandleId]);

  return (
    <>
      <defs>
        <linearGradient id={`grad-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={colors.glow} stopOpacity="0.8" />
          <stop offset="100%" stopColor={colors.glow} stopOpacity="0.4" />
        </linearGradient>
      </defs>
      {/* Background glow */}
      <path
        d={edgePath}
        fill="none"
        stroke={`${colors.glow}22`}
        strokeWidth={8}
        style={{ filter: 'blur(4px)' }}
      />
      {/* Main edge */}
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={`url(#grad-${id})`}
        strokeWidth={2}
        markerEnd={markerEnd}
        style={style}
      />
      {/* Animated dot */}
      <circle r={3} fill={colors.glow}>
        <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
      </circle>
      {/* Data flow label */}
      {label && (
        <EdgeLabelRenderer>
          <div
            className="edge-label"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'none',
              backgroundColor: colors.bg,
              color: colors.text,
              border: `1px solid ${colors.text}33`,
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '10px',
              fontWeight: 600,
              letterSpacing: '0.5px',
              textTransform: 'uppercase',
              whiteSpace: 'nowrap',
              backdropFilter: 'blur(4px)',
              boxShadow: `0 0 8px ${colors.glow}22`,
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
