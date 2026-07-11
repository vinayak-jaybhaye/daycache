"use client";

import React from "react";
import { motion } from "framer-motion";
import type { Editor } from "@tiptap/react";
import { Image as ImageIcon, Undo2, Redo2 } from "lucide-react";

interface FloatingToolbarProps {
  editor: Editor;
  onImageUpload: () => void;
}

/**
 * FloatingToolbar — bottom floating action bar.
 * Provides: Image upload, Undo, Redo, Horizontal Rule.
 */
export const FloatingToolbar: React.FC<FloatingToolbarProps> = ({ editor, onImageUpload }) => {
  return (
    <motion.div
      initial={{ y: 50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.3 }}
      className="glass-panel fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 gap-4 rounded-full border border-[var(--border-soft)] px-4 py-2.5 shadow-2xl sm:bottom-8 sm:gap-6 sm:px-6 sm:py-3"
    >
      <button
        onClick={onImageUpload}
        className="text-[var(--ink-color)] transition-colors hover:text-[var(--accent-color)]"
        title="Insert image"
      >
        <ImageIcon size={20} />
      </button>
      <button
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        className="text-[var(--ink-color)] transition-colors hover:text-[var(--accent-color)] disabled:opacity-30"
        title="Undo"
      >
        <Undo2 size={20} />
      </button>
      <button
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        className="text-[var(--ink-color)] transition-colors hover:text-[var(--accent-color)] disabled:opacity-30"
        title="Redo"
      >
        <Redo2 size={20} />
      </button>
    </motion.div>
  );
};
