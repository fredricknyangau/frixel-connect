/**
 * src/components/shared/AnimatedCheckmark.tsx
 * =============================================
 * SVG checkmark that draws itself on mount using CSS stroke-dashoffset animation.
 * No animation libraries — pure CSS keyframe on the SVG path's stroke-dasharray.
 *
 * HOW THE ANIMATION WORKS:
 *   SVG paths have a `stroke-dasharray` property that creates dashes in the stroke.
 *   Setting `stroke-dashoffset` equal to the total path length makes the entire
 *   stroke "disappear" (the gap is the full length of the path).
 *   Animating dashoffset from pathLength → 0 causes the stroke to "draw itself"
 *   from start to end, creating the signature "writing" checkmark effect.
 *
 * REUSABILITY:
 *   This component was designed for the router onboarding complete screen but
 *   can also be used in PaymentStatusPage for the confirmed payment state,
 *   voucher redemption, or any other success flow.
 *
 * Props:
 *   size?   — diameter in pixels (default: 80)
 *   color?  — CSS color string (default: ZealSync primary oklch(0.72 0.18 188))
 */

import { useEffect, useRef } from 'react';

interface AnimatedCheckmarkProps {
  size?: number;
  color?: string;
}

export function AnimatedCheckmark({
  size = 80,
  color = 'oklch(0.72 0.18 188)',
}: AnimatedCheckmarkProps) {
  const circleRef = useRef<SVGCircleElement>(null);
  const checkRef = useRef<SVGPolylineElement>(null);

  useEffect(() => {
    // The style block injects the @keyframes rule into the document's
    // <head> on first render. This avoids a separate CSS file dependency
    // while keeping the animation performant (GPU-composited transform).
    const styleId = 'animated-checkmark-styles';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        @keyframes zealsync-circle-draw {
          0% {
            stroke-dashoffset: 166;
            opacity: 0;
          }
          10% { opacity: 1; }
          100% {
            stroke-dashoffset: 0;
          }
        }

        @keyframes zealsync-check-draw {
          0%, 30% {
            stroke-dashoffset: 48;
            opacity: 0;
          }
          35% { opacity: 1; }
          100% {
            stroke-dashoffset: 0;
          }
        }

        .zs-checkmark-circle {
          stroke-dasharray: 166;
          stroke-dashoffset: 166;
          animation: zealsync-circle-draw 0.6s cubic-bezier(0.65, 0, 0.45, 1) forwards;
        }

        .zs-checkmark-check {
          stroke-dasharray: 48;
          stroke-dashoffset: 48;
          animation: zealsync-check-draw 0.6s cubic-bezier(0.65, 0, 0.45, 1) 0.1s forwards;
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const viewBox = 52; // Coordinate space
  const strokeWidth = 2.5;
  const radius = (viewBox - strokeWidth) / 2;
  const cx = viewBox / 2;
  const cy = viewBox / 2;

  return (
    <div
      style={{ width: size, height: size }}
      role="img"
      aria-label="Setup complete checkmark"
    >
      <svg
        viewBox={`0 0 ${viewBox} ${viewBox}`}
        width={size}
        height={size}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Faint background circle */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          opacity={0.15}
        />

        {/* Animated circle that draws clockwise */}
        <circle
          ref={circleRef}
          className="zs-checkmark-circle"
          cx={cx}
          cy={cy}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          // Start from the top (12 o'clock) by rotating -90 degrees
          transform={`rotate(-90, ${cx}, ${cy})`}
        />

        {/* Animated checkmark stroke */}
        <polyline
          ref={checkRef}
          className="zs-checkmark-check"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
          // Points chosen for an aesthetically balanced checkmark within a 52x52 viewBox
          points="14,28 22,36 38,18"
        />
      </svg>
    </div>
  );
}

export default AnimatedCheckmark;
