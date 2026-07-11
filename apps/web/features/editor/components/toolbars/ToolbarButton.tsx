/**
 * ToolbarButton — Reusable button component for editor toolbars.
 * Handles active state, tooltips, and accessibility.
 */

import React from "react";

interface ToolbarButtonProps {
  /** Click handler */
  onClick: () => void;

  /** Whether the button represents an active format */
  isActive?: boolean;

  /** Button is disabled */
  isDisabled?: boolean;

  /** Icon or content to display */
  children: React.ReactNode;

  /** Tooltip text on hover */
  title?: string;

  /** CSS classes for custom styling */
  className?: string;

  /** Button size variant */
  size?: "sm" | "md" | "lg";

  /** Show loading state */
  isLoading?: boolean;

  /** ARIA label for accessibility */
  ariaLabel?: string;
}

/**
 * Toolbar button with active state, tooltip, and accessibility features.
 */
export const ToolbarButton: React.FC<ToolbarButtonProps> = ({
  onClick,
  isActive = false,
  isDisabled = false,
  children,
  title,
  className = "",
  size = "md",
  isLoading = false,
  ariaLabel,
}) => {
  const sizeClasses = {
    sm: "p-1.5 text-xs",
    md: "p-2 text-sm",
    lg: "p-2.5 text-base",
  };

  const baseClasses = `
    inline-flex items-center justify-center
    rounded transition-colors duration-200
    ${sizeClasses[size]}
    ${isActive ? "bg-[var(--border-soft)] text-[var(--accent-color)]" : "text-[var(--ink-color)]"}
    ${isDisabled ? "cursor-not-allowed opacity-50" : "hover:bg-[var(--border-soft)] cursor-pointer"}
    ${isLoading ? "opacity-75" : ""}
    ${className}
  `;

  return (
    <button
      onClick={onClick}
      disabled={isDisabled || isLoading}
      title={title}
      aria-label={ariaLabel || title}
      aria-pressed={isActive}
      className={baseClasses}
    >
      {isLoading ? (
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : (
        children
      )}
    </button>
  );
};
