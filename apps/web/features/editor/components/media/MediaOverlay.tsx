/**
 * MediaOverlay — Hover toolbar for media nodes.
 * Shows actions like download, replace, delete when hovering over images.
 */

import React, { useState } from "react";
import { Download, Trash2, Edit2 } from "lucide-react";

interface MediaOverlayProps {
  /** Whether the overlay should be visible */
  isVisible: boolean;

  /** Image URL for download link */
  imageUrl?: string;

  /** Callback when user clicks delete */
  onDelete?: () => void;

  /** Callback when user clicks edit/replace */
  onEdit?: () => void;

  /** CSS classes for positioning */
  className?: string;
}

/**
 * Hover toolbar overlay for media actions.
 * Appears on top of the image when hovering.
 */
export const MediaOverlay: React.FC<MediaOverlayProps> = ({
  isVisible,
  imageUrl,
  onDelete,
  onEdit,
  className = "",
}) => {
  const [showActions, setShowActions] = useState(false);

  if (!isVisible) return null;

  return (
    <div
      className={`absolute inset-0 flex items-center justify-center rounded-lg bg-black/30 opacity-0 transition-opacity ${showActions ? "opacity-100" : ""} ${className}`}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div className="flex gap-2">
        {/* Download */}
        {imageUrl && (
          <a
            href={imageUrl}
            download
            className="rounded bg-white/90 p-2 text-gray-800 transition-colors hover:bg-white"
            title="Download"
          >
            <Download size={16} />
          </a>
        )}

        {/* Edit/Replace */}
        {onEdit && (
          <button
            onClick={onEdit}
            className="rounded bg-white/90 p-2 text-gray-800 transition-colors hover:bg-white"
            title="Replace image"
          >
            <Edit2 size={16} />
          </button>
        )}

        {/* Delete */}
        {onDelete && (
          <button
            onClick={onDelete}
            className="rounded bg-white/90 p-2 text-gray-800 transition-colors hover:bg-white"
            title="Delete"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
};
