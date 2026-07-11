/**
 * MediaUploadProgress — Shows upload progress with ring indicator.
 * Displays percentage and allows cancellation.
 */

import React, { useMemo } from "react";
import { X } from "lucide-react";

interface MediaUploadProgressProps {
  /** Upload progress from 0-100 */
  progress: number;

  /** Show checkmark when complete (100%) */
  isComplete?: boolean;

  /** Callback when user clicks cancel */
  onCancel?: () => void;

  /** Size of the progress ring */
  size?: number;

  /** Optional label to show below the ring */
  label?: string;
}

/**
 * Circular progress ring using SVG.
 * Smooth animation from 0-100% during upload.
 */
export const MediaUploadProgress: React.FC<MediaUploadProgressProps> = ({
  progress,
  isComplete = false,
  onCancel,
  size = 48,
  label,
}) => {
  const radius = size / 2 - 4; // Leave room for stroke
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  const displayProgress = useMemo(() => {
    if (isComplete) return 100;
    return Math.min(Math.max(progress, 0), 100);
  }, [progress, isComplete]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Background circle */}
        <svg
          className="absolute inset-0"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--border-soft)"
            strokeWidth="2"
          />
        </svg>

        {/* Progress circle */}
        <svg
          className="absolute inset-0"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--accent-color)"
            strokeWidth="2"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{
              transition: "stroke-dashoffset 0.3s ease",
              transform: "rotate(-90deg)",
              transformOrigin: `${size / 2}px ${size / 2}px`,
            }}
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex items-center justify-center">
          {isComplete ? (
            <div className="text-sm font-medium text-[var(--accent-color)]">✓</div>
          ) : (
            <div className="text-xs font-medium text-[var(--text-muted)]">{displayProgress}%</div>
          )}
        </div>

        {/* Cancel button */}
        {!isComplete && onCancel && (
          <button
            onClick={onCancel}
            className="absolute -top-2 -right-2 rounded-full p-1 text-[var(--text-muted)] transition-colors hover:bg-[var(--border-soft)] hover:text-[var(--ink-color)]"
            aria-label="Cancel upload"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {label && <div className="text-xs text-[var(--text-muted)]">{label}</div>}
    </div>
  );
};
