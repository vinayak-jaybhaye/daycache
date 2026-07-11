/**
 * KeyboardHints — Shows available keyboard shortcuts to the user.
 * Can be displayed as a modal, popover, or help section.
 */

import React, { useMemo } from "react";
import { X } from "lucide-react";
import {
  KEYBOARD_SHORTCUTS,
  getShortcutsByCategory,
  formatShortcutForDisplay,
} from "../../utils/keyboardShortcuts";
import type { KeyboardShortcut } from "../../utils/keyboardShortcuts";

interface KeyboardHintsProps {
  /** Whether the hints panel is visible */
  isOpen: boolean;

  /** Callback to close the panel */
  onClose: () => void;

  /** Filter by specific category */
  category?: KeyboardShortcut["category"];

  /** Show as a modal overlay or as a popover */
  mode?: "modal" | "popover";
}

/**
 * Grouped keyboard shortcuts help panel.
 * Shows available shortcuts organized by category.
 */
export const KeyboardHints: React.FC<KeyboardHintsProps> = ({
  isOpen,
  onClose,
  category,
  mode = "modal",
}) => {
  const shortcuts = useMemo(() => {
    if (category) {
      return getShortcutsByCategory(category);
    }
    return KEYBOARD_SHORTCUTS;
  }, [category]);

  const grouped = useMemo(() => {
    const groups: Record<string, KeyboardShortcut[]> = {};

    for (const shortcut of shortcuts) {
      if (!groups[shortcut.category]) {
        groups[shortcut.category] = [];
      }
      groups[shortcut.category].push(shortcut);
    }

    return groups;
  }, [shortcuts]);

  if (!isOpen) return null;

  const categoryLabels: Record<string, string> = {
    formatting: "Text Formatting",
    block: "Block Types",
    list: "Lists",
    navigation: "Navigation",
    media: "Media",
  };

  const content = (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--ink-color)]">Keyboard Shortcuts</h2>
        <button
          onClick={onClose}
          className="rounded p-1 text-[var(--text-muted)] transition-colors hover:bg-[var(--border-soft)]"
          aria-label="Close"
        >
          <X size={20} />
        </button>
      </div>

      {/* Shortcuts by category */}
      <div className="space-y-4">
        {Object.entries(grouped).map(([cat, items]) => (
          <div key={cat}>
            <h3 className="mb-2 text-sm font-medium tracking-wide text-[var(--text-muted)] uppercase">
              {categoryLabels[cat] || cat}
            </h3>
            <div className={`grid gap-2 ${mode === "modal" ? "sm:grid-cols-2" : "grid-cols-1"}`}>
              {items.map((shortcut) => (
                <div key={shortcut.name} className="rounded bg-[var(--border-soft)] p-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium text-[var(--ink-color)]">
                        {shortcut.name}
                      </div>
                      {shortcut.description && (
                        <div className="text-xs text-[var(--text-muted)]">
                          {shortcut.description}
                        </div>
                      )}
                    </div>
                    {shortcut.keys && (
                      <div className="flex-shrink-0 rounded border border-[var(--border-soft)] bg-white/50 px-2 py-1 font-mono text-xs font-semibold text-[var(--ink-color)] dark:bg-black/50">
                        {formatShortcutForDisplay(shortcut.keys)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Footer hint */}
      <div className="rounded bg-[var(--border-soft)] p-3 text-xs text-[var(--text-muted)]">
        💡 Tip: Type <code className="font-mono">/ </code> in the editor to see all available
        commands
      </div>
    </div>
  );

  if (mode === "modal") {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
        <div className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-lg dark:bg-slate-950">
          {content}
        </div>
      </div>
    );
  }

  // Popover mode
  return (
    <div className="absolute right-0 bottom-full z-40 mb-2 max-h-[60vh] w-80 overflow-y-auto rounded-lg border border-[var(--border-soft)] bg-[var(--card-bg)] p-4 shadow-lg backdrop-blur-md">
      {content}
    </div>
  );
};
