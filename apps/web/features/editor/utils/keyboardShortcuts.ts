/**
 * Keyboard shortcut definitions and helpers.
 * Centralizes all keyboard shortcut mappings for the editor.
 */

export interface KeyboardShortcut {
  name: string;
  description: string;
  keys: string; // e.g., "Mod-b", "Ctrl-k", "Shift-Alt-t"
  category: "formatting" | "block" | "list" | "navigation" | "media";
}

/**
 * Standard keyboard shortcuts for the editor.
 * Uses TipTap convention: "Mod" = Cmd on Mac, Ctrl on Windows/Linux.
 */
export const KEYBOARD_SHORTCUTS: KeyboardShortcut[] = [
  // Formatting
  { name: "Bold", description: "Make text bold", keys: "Mod-b", category: "formatting" },
  { name: "Italic", description: "Make text italic", keys: "Mod-i", category: "formatting" },
  {
    name: "Strikethrough",
    description: "Strike through text",
    keys: "Mod-Shift-x",
    category: "formatting",
  },
  { name: "Code", description: "Inline code", keys: "Mod-e", category: "formatting" },
  {
    name: "Clear Formatting",
    description: "Remove all formatting",
    keys: "Mod-\\",
    category: "formatting",
  },

  // Blocks
  { name: "Paragraph", description: "Switch to paragraph", keys: "Mod-Alt-0", category: "block" },
  { name: "Heading 1", description: "Switch to heading 1", keys: "Mod-Alt-1", category: "block" },
  { name: "Heading 2", description: "Switch to heading 2", keys: "Mod-Alt-2", category: "block" },
  { name: "Heading 3", description: "Switch to heading 3", keys: "Mod-Alt-3", category: "block" },
  {
    name: "Code Block",
    description: "Insert code block",
    keys: "Mod-Alt-c",
    category: "block",
  },
  {
    name: "Blockquote",
    description: "Insert blockquote",
    keys: "Mod-Shift-b",
    category: "block",
  },
  {
    name: "Horizontal Rule",
    description: "Insert horizontal rule",
    keys: "Mod-Shift-5",
    category: "block",
  },

  // Lists
  {
    name: "Bullet List",
    description: "Toggle bullet list",
    keys: "Mod-Shift-u",
    category: "list",
  },
  {
    name: "Ordered List",
    description: "Toggle ordered list",
    keys: "Mod-Shift-o",
    category: "list",
  },
  {
    name: "Task List",
    description: "Toggle task list",
    keys: "Mod-Shift-t",
    category: "list",
  },

  // Navigation
  {
    name: "Slash Command",
    description: "Open slash command menu",
    keys: "Slash",
    category: "navigation",
  },
  { name: "Undo", description: "Undo last action", keys: "Mod-z", category: "navigation" },
  { name: "Redo", description: "Redo last action", keys: "Mod-Shift-z", category: "navigation" },

  // Media
  {
    name: "Insert Image",
    description: "Insert an image",
    keys: "Mod-Shift-i",
    category: "media",
  },
];

/**
 * Markdown shortcuts that convert text as you type.
 * e.g., "## " → heading 2
 */
export const MARKDOWN_SHORTCUTS = [
  { text: "# ", command: "heading", level: 1 },
  { text: "## ", command: "heading", level: 2 },
  { text: "### ", command: "heading", level: 3 },
  { text: "#### ", command: "heading", level: 4 },
  { text: "> ", command: "blockquote" },
  { text: "* ", command: "bullet_list" },
  { text: "- ", command: "bullet_list" },
  { text: "+ ", command: "bullet_list" },
  { text: "1. ", command: "ordered_list" },
  { text: "[] ", command: "task_list" },
  { text: "``` ", command: "code_block" },
];

/**
 * Format a keyboard shortcut for display.
 * Converts "Mod-b" to "⌘B" on Mac or "Ctrl+B" on Windows.
 */
export function formatShortcutForDisplay(shortcut: string): string {
  const isMac = typeof window !== "undefined" && navigator.platform.toUpperCase().includes("MAC");

  const formatted = shortcut
    .replace(/Mod/g, isMac ? "⌘" : "Ctrl")
    .replace(/Shift/g, "Shift")
    .replace(/Alt/g, isMac ? "⌥" : "Alt")
    .replace(/Ctrl/g, "Ctrl")
    .replace(/-/g, isMac ? "" : "+");

  return formatted;
}

/**
 * Get all shortcuts for a specific category.
 */
export function getShortcutsByCategory(category: KeyboardShortcut["category"]): KeyboardShortcut[] {
  return KEYBOARD_SHORTCUTS.filter((s) => s.category === category);
}

/**
 * Find a shortcut by name.
 */
export function findShortcutByName(name: string): KeyboardShortcut | undefined {
  return KEYBOARD_SHORTCUTS.find((s) => s.name === name);
}

/**
 * Create a keyboard event handler helper.
 * Returns true if the event matches the shortcut pattern.
 */
export function matchesShortcut(event: KeyboardEvent, pattern: string): boolean {
  const parts = pattern.toLowerCase().split("-");

  for (const part of parts) {
    switch (part) {
      case "mod":
        if (!event.metaKey && !event.ctrlKey) return false;
        break;
      case "ctrl":
        if (!event.ctrlKey) return false;
        break;
      case "shift":
        if (!event.shiftKey) return false;
        break;
      case "alt":
        if (!event.altKey) return false;
        break;
      default:
        // Check key code
        if (event.key.toLowerCase() !== part) return false;
    }
  }

  return true;
}

/**
 * Check if a key event is composing (used by CJK IMEs).
 * Don't trigger commands while composing.
 */
export function isComposingEvent(event: KeyboardEvent): boolean {
  return event.isComposing || event.keyCode === 229;
}

/**
 * Get human-readable description of a key event.
 */
export function describeKeyEvent(event: KeyboardEvent): string {
  const parts: string[] = [];

  if (event.ctrlKey) parts.push("Ctrl");
  if (event.altKey) parts.push("Alt");
  if (event.shiftKey) parts.push("Shift");
  if (event.metaKey) parts.push("Cmd");

  const key = event.key === " " ? "Space" : event.key;
  parts.push(key);

  return parts.join("+");
}
