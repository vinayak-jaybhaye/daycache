/**
 * ToolbarDivider — Visual separator between toolbar button groups.
 */

import React from "react";

interface ToolbarDividerProps {
  /** Orientation: vertical (for row) or horizontal (for column) */
  orientation?: "vertical" | "horizontal";

  /** CSS classes for custom styling */
  className?: string;
}

/**
 * Visual divider for grouping toolbar buttons.
 */
export const ToolbarDivider: React.FC<ToolbarDividerProps> = ({
  orientation = "vertical",
  className = "",
}) => {
  const classes =
    orientation === "vertical"
      ? `mx-1 my-1 w-px h-6 bg-[var(--border-soft)] ${className}`
      : `mx-1 my-1 h-px w-6 bg-[var(--border-soft)] ${className}`;

  return <div className={classes} />;
};
