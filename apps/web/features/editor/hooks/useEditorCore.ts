/**
 * useEditorCore — Main editor initialization hook.
 *
 * Consolidates editor creation, configuration, and extension setup.
 * Returns a fully-initialized TipTap editor with all extensions configured.
 */

import { useMemo } from "react";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Link from "@tiptap/extension-link";

import { MediaImage } from "../extensions/MediaImage";
import { SlashCommandExtension, getSlashSuggestionConfig } from "../extensions/SlashCommand";
import type { Editor } from "@tiptap/react";
import type { MediaResolver } from "../types";

export interface UseEditorCoreOptions {
  /** Initial document content */
  content?: string | Record<string, unknown>;

  /** Editor placeholder text */
  placeholder?: string;

  /** Font CSS class (e.g., "font-serif", "font-sans") */
  fontClass?: string;

  /** Media resolver for resolving image metadata */
  mediaResolver?: MediaResolver;

  /** Callback to trigger file picker for slash commands */
  onImageUpload?: () => void;

  /** Paste handler for handling pasted content */
  handlePaste?: (view: unknown, event: ClipboardEvent) => boolean;

  /** Drop handler for handling dropped content */
  handleDrop?: (view: unknown, event: DragEvent, slice: unknown, moved: boolean) => boolean;

  /** Whether editor should be editable */
  editable?: boolean;
}

/**
 * Create a fully-configured TipTap editor.
 * This hook manages all extension setup and editor lifecycle.
 */
export function useEditorCore(options: UseEditorCoreOptions): Editor | null {
  const {
    content = "",
    placeholder = "Start writing... Type '/' for commands",
    fontClass = "font-serif",
    mediaResolver,
    onImageUpload,
    handlePaste,
    handleDrop,
    editable = true,
  } = options;

  const editor = useEditor({
    immediatelyRender: false,
    editable,
    extensions: [
      // Core formatting
      StarterKit.configure({
        link: false,
      }),

      // Task lists
      TaskList,
      TaskItem.configure({
        nested: true,
      }),

      // Links
      Link.configure({
        openOnClick: false,
        autolink: true,
        defaultProtocol: "https",
      }),

      // Custom media image node
      MediaImage,

      // Placeholder text
      Placeholder.configure({
        placeholder,
      }),

      // Slash command menu
      SlashCommandExtension.configure({
        context: {
          triggerImageUpload: onImageUpload ?? (() => {}),
        },
        suggestion: getSlashSuggestionConfig(),
      }),
    ],

    // Initial content
    content:
      content && typeof content === "object" && content.type === "doc"
        ? content
        : typeof content === "string"
          ? content
          : "",

    // Editor attributes and styling
    editorProps: {
      attributes: {
        class: `w-full bg-transparent border-none outline-none ${fontClass} text-xl md:text-2xl leading-relaxed text-[var(--ink-color)] placeholder:text-[var(--text-muted)] placeholder:opacity-50 min-h-[50vh]`,
      },

      // Handle pasted content
      handlePaste: handlePaste ?? (() => false),

      // Handle dropped content
      handleDrop: handleDrop ?? (() => false),
    },
  });

  // Set media resolver on storage after editor is created
  useMemo(() => {
    if (editor && mediaResolver) {
      const storage = (editor.storage as unknown as Record<string, unknown>).mediaImage as
        { resolver?: MediaResolver } | undefined;
      if (storage) {
        // eslint-disable-next-line react-hooks/immutability
        storage.resolver = mediaResolver;
      }
    }
  }, [editor, mediaResolver]);

  return editor;
}
