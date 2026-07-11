/**
 * useEditorShortcuts — Comprehensive keyboard shortcut management.
 *
 * Registers custom keyboard shortcuts on the editor instance.
 * Includes markdown shortcuts (## → heading), command shortcuts, and more.
 */

import { useEffect, useRef } from "react";
import type { Editor } from "@tiptap/react";
import { getCurrentBlockText } from "../utils/editorHelpers";
import { MARKDOWN_SHORTCUTS } from "../utils/keyboardShortcuts";

export interface UseEditorShortcutsOptions {
  /** Enable markdown shortcuts */
  enableMarkdownShortcuts?: boolean;

  /** Enable keyboard command shortcuts */
  enableCommandShortcuts?: boolean;

  /** Callback when image upload shortcut is triggered */
  onImageUploadShortcut?: () => void;
}

/**
 * Register keyboard shortcuts on the editor.
 * Manages markdown shortcuts, command shortcuts, and custom handlers.
 */
export function useEditorShortcuts(editor: Editor | null, options: UseEditorShortcutsOptions = {}) {
  const {
    enableMarkdownShortcuts = true,
    enableCommandShortcuts = true,
    onImageUploadShortcut,
  } = options;

  const editorRef = useRef(editor);
  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);

  // Register markdown shortcuts
  useEffect(() => {
    if (!editor || !enableMarkdownShortcuts || !editor.view?.dom) return;

    // Listen for space key to trigger markdown shortcuts
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== " " || event.ctrlKey || event.metaKey || event.altKey) return;

      const currentEditor = editorRef.current;
      if (!currentEditor) return;

      const text = getCurrentBlockText(currentEditor);

      // Check for markdown patterns
      for (const shortcut of MARKDOWN_SHORTCUTS) {
        if (text === shortcut.text) {
          event.preventDefault();

          // Remove the trigger text
          currentEditor
            .chain()
            .focus()
            .deleteRange({ from: 1, to: text.length + 1 })
            .run();

          // Apply the command
          switch (shortcut.command) {
            case "heading":
              if (shortcut.level) {
                currentEditor
                  .chain()
                  .focus()
                  .setHeading({ level: shortcut.level as 1 | 2 | 3 })
                  .run();
              }
              break;
            case "blockquote":
              currentEditor.chain().focus().setBlockquote().run();
              break;
            case "bullet_list":
              currentEditor.chain().focus().toggleBulletList().run();
              break;
            case "ordered_list":
              currentEditor.chain().focus().toggleOrderedList().run();
              break;
            case "task_list":
              currentEditor.chain().focus().toggleTaskList().run();
              break;
            case "code_block":
              currentEditor.chain().focus().toggleCodeBlock().run();
              break;
          }

          return;
        }
      }
    };

    const dom = editor.view.dom;
    dom.addEventListener("keydown", handleKeyDown);

    return () => {
      dom.removeEventListener("keydown", handleKeyDown);
    };
  }, [editor, enableMarkdownShortcuts]);

  // Register command shortcuts via keyboard handler
  useEffect(() => {
    if (!editor || !enableCommandShortcuts || !editor.view?.dom) return;

    const handleCommandShortcuts = (event: KeyboardEvent) => {
      const isMod = event.ctrlKey || event.metaKey;
      const isShift = event.shiftKey;
      const isAlt = event.altKey;

      // Ctrl/Cmd + Shift + I → Insert image
      if (isMod && isShift && event.key.toLowerCase() === "i") {
        event.preventDefault();
        onImageUploadShortcut?.();
        return;
      }

      // Ctrl/Cmd + Alt + 0 → Paragraph
      if (isMod && isAlt && event.key === "0") {
        event.preventDefault();
        editor.chain().focus().setParagraph().run();
        return;
      }

      // Ctrl/Cmd + Alt + 1-3 → Heading levels
      if (isMod && isAlt && (event.key === "1" || event.key === "2" || event.key === "3")) {
        event.preventDefault();
        const level = parseInt(event.key) as 1 | 2 | 3;
        editor.chain().focus().setHeading({ level }).run();
        return;
      }

      // Ctrl/Cmd + Shift + U → Bullet list
      if (isMod && isShift && event.key.toLowerCase() === "u") {
        event.preventDefault();
        editor.chain().focus().toggleBulletList().run();
        return;
      }

      // Ctrl/Cmd + Shift + O → Ordered list
      if (isMod && isShift && event.key.toLowerCase() === "o") {
        event.preventDefault();
        editor.chain().focus().toggleOrderedList().run();
        return;
      }

      // Ctrl/Cmd + Shift + T → Task list
      if (isMod && isShift && event.key.toLowerCase() === "t") {
        event.preventDefault();
        editor.chain().focus().toggleTaskList().run();
        return;
      }

      // Ctrl/Cmd + Shift + B → Blockquote
      if (isMod && isShift && event.key.toLowerCase() === "b") {
        event.preventDefault();
        editor.chain().focus().toggleBlockquote().run();
        return;
      }

      // Ctrl/Cmd + Alt + C → Code block
      if (isMod && isAlt && event.key.toLowerCase() === "c") {
        event.preventDefault();
        editor.chain().focus().toggleCodeBlock().run();
        return;
      }
    };

    const dom = editor.view.dom;
    dom.addEventListener("keydown", handleCommandShortcuts);

    return () => {
      dom.removeEventListener("keydown", handleCommandShortcuts);
    };
  }, [editor, enableCommandShortcuts, onImageUploadShortcut]);
}
