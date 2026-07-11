/**
 * MediaErrorState — Shows error message with retry button.
 * Displayed when media upload fails.
 */

import React from "react";
import { AlertTriangle, RotateCcw, X } from "lucide-react";

interface MediaErrorStateProps {
  /** Error message to display */
  error: string;

  /** Callback when user clicks retry */
  onRetry?: () => void;

  /** Callback when user clicks delete/remove */
  onRemove?: () => void;

  /** Optional size customization */
  size?: "sm" | "md" | "lg";
}

/**
 * Error display with retry and remove actions.
 */
export const MediaErrorState: React.FC<MediaErrorStateProps> = ({
  error,
  onRetry,
  onRemove,
  size = "md",
}) => {
  const sizeClasses = {
    sm: "gap-2 p-2",
    md: "gap-3 p-4",
    lg: "gap-4 p-6",
  };

  const iconSize = {
    sm: 14,
    md: 16,
    lg: 20,
  };

  return (
    <div
      className={`flex flex-col rounded-lg border border-[var(--error-border)] bg-[var(--error-bg)] ${sizeClasses[size]}`}
    >
      {/* Error header */}
      <div className="flex items-start gap-2">
        <AlertTriangle
          size={iconSize[size]}
          className="mt-0.5 flex-shrink-0 text-[var(--error-color)]"
        />
        <div className="flex-1">
          <p className="text-sm font-medium text-[var(--error-color)]">Upload failed</p>
          <p className="text-xs text-[var(--error-text)]">{error}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-[var(--error-color)] transition-colors hover:bg-[var(--error-hover)]"
          >
            <RotateCcw size={12} />
            Retry
          </button>
        )}

        {onRemove && (
          <button
            onClick={onRemove}
            className="flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--border-soft)]"
          >
            <X size={12} />
            Remove
          </button>
        )}
      </div>
    </div>
  );
};
