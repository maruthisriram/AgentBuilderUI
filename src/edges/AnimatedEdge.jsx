import React from 'react';
import { getBezierPath } from 'reactflow';

export default function AnimatedEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <defs>
        <linearGradient id={`grad-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      {/* Background glow */}
      <path
        d={edgePath}
        fill="none"
        stroke="rgba(139, 92, 246, 0.15)"
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
      <circle r={3} fill="#8b5cf6">
        <animateMotion dur="2s" repeatCount="indefinite" path={edgePath} />
      </circle>
    </>
  );
}
