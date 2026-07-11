/**
 * FloatingToolbar — Floating toolbar with undo/redo and media upload.
 * Positioned in the bottom-right corner of the editor.
 */

import React, { useState, useRef } from "react";
import { Undo, Redo, Image as ImageIcon, HelpCircle } from "lucide-react";
import type { Editor } from "@tiptap/react";
import { ToolbarButton } from "./ToolbarButton";
import { ToolbarDivider } from "./ToolbarDivider";
import { KeyboardHints } from "./KeyboardHints";
import { useOnClickOutside } from "@/hooks/useOnClickOutside";

interface FloatingToolbarProps {
  /** TipTap editor instance */
  editor: Editor;

  /** Callback to trigger image upload */
  onImageUpload: () => void;

  /** CSS classes for custom positioning */
  className?: string;
}

/**
 * Floating toolbar with essential editor actions.
 * Appears in a fixed position at the bottom-right of the viewport.
 */
export const FloatingToolbar: React.FC<FloatingToolbarProps> = ({
  editor,
  onImageUpload,
  className = "",
}) => {
  const [showHints, setShowHints] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useOnClickOutside(containerRef, () => {
    if (showHints) setShowHints(false);
  });

  return (
    <div ref={containerRef}>
      {/* Floating toolbar */}
      <div
        className={`fixed right-6 bottom-6 z-45 flex gap-1 rounded-lg border border-[var(--border-soft)] bg-[var(--card-bg)] p-1 shadow-lg backdrop-blur-sm ${className}`}
      >
        <ToolbarButton
          onClick={() => editor.chain().focus().undo().run()}
          isDisabled={!editor.can().undo()}
          title="Undo (Ctrl+Z)"
          size="md"
        >
          <Undo size={18} />
        </ToolbarButton>

        <ToolbarButton
          onClick={() => editor.chain().focus().redo().run()}
          isDisabled={!editor.can().redo()}
          title="Redo (Ctrl+Shift+Z)"
          size="md"
        >
          <Redo size={18} />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton onClick={onImageUpload} title="Upload image (Ctrl+Shift+I)" size="md">
          <ImageIcon size={18} />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          onClick={() => setShowHints(!showHints)}
          isActive={showHints}
          title="Keyboard shortcuts"
          size="md"
        >
          <HelpCircle size={18} />
        </ToolbarButton>
      </div>

      {/* Keyboard hints popover */}
      <div className="fixed right-6 bottom-20 z-50">
        <KeyboardHints isOpen={showHints} onClose={() => setShowHints(false)} mode="popover" />
      </div>
    </div>
  );
};
