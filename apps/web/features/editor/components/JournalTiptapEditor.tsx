"use client";

import React, { useEffect, useMemo, useRef } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Link from "@tiptap/extension-link";
import type { JournalEntryResponse } from "@/lib/api/entries";
import { SlashCommandExtension, getSlashSuggestionConfig } from "../extensions/SlashCommand";
import { MediaImage } from "../extensions/MediaImage";
import type { MediaImageStorage, MediaResolver } from "../extensions/MediaImage";
import { useAutoSave } from "../hooks/useAutoSave";
import { useMediaUpload } from "../hooks/useMediaUpload";
import { normalizeEditorContent } from "../utils/content";
import { BubbleToolbar } from "./BubbleToolbar";
import { FloatingToolbar } from "./FloatingToolbar";

interface JournalTiptapEditorProps {
  activeEntryId: string | null;
  content: JournalEntryResponse["content"] | null | undefined;
  contentText?: string | null;
  title: string;
  fontClass: string;
  resolver: MediaResolver;
  onSavingChange: (isSaving: boolean) => void;
}

const editorClass =
  "w-full min-h-[50vh] border-none bg-transparent text-xl leading-relaxed text-[var(--ink-color)] outline-none placeholder:text-[var(--text-muted)] placeholder:opacity-50 md:text-2xl";

export const JournalTiptapEditor: React.FC<JournalTiptapEditorProps> = ({
  activeEntryId,
  content,
  contentText,
  title,
  fontClass,
  resolver,
  onSavingChange,
}) => {
  const mediaUploadRef = useRef<ReturnType<typeof useMediaUpload> | null>(null);
  const syncedEntryRef = useRef({
    id: activeEntryId,
    hasServerContent: hasServerContent(content, contentText),
  });

  const triggerImageUpload = useCallback(() => {
    mediaUploadRef.current?.triggerFilePicker();
  }, []);

  const extensions = useMemo(
    () => [
      StarterKit.configure({
        link: false,
      }),
      TaskList,
      TaskItem.configure({
        nested: true,
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        defaultProtocol: "https",
      }),
      MediaImage,
      Placeholder.configure({
        placeholder: "Start writing... Type '/' for commands",
      }),
      // eslint-disable-next-line react-hooks/refs
      SlashCommandExtension.configure({
        context: { triggerImageUpload },
        suggestion: getSlashSuggestionConfig(),
      }),
    ],
    [triggerImageUpload],
  );

  const editor = useEditor({
    immediatelyRender: false,
    shouldRerenderOnTransaction: false,
    extensions,
    content: normalizeEditorContent(content, contentText),
    editorProps: {
      attributes: {
        class: editorClass,
        "aria-label": "Journal entry body",
      },
      handlePaste: (view, event) => mediaUploadRef.current?.handlePaste(view, event) ?? false,
      handleDrop: (view, event, slice, moved) =>
        mediaUploadRef.current?.handleDrop(view, event, slice, moved) ?? false,
    },
    onContentError({ error }) {
      console.error("Tiptap content did not match the editor schema:", error);
    },
  });

  const mediaUpload = useMediaUpload(editor);
  useEffect(() => {
    mediaUploadRef.current = mediaUpload;
  }, [mediaUpload]);

  const { isSaving } = useAutoSave(editor, title, activeEntryId);

  useEffect(() => {
    onSavingChange(isSaving);
  }, [isSaving, onSavingChange]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;

    const storage = (editor.storage as Record<string, unknown>).mediaImage as
      MediaImageStorage | undefined;

    if (storage) {
      // eslint-disable-next-line react-hooks/immutability
      storage.resolver = resolver;
    }
  }, [editor, resolver]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;

    const nextHasServerContent = hasServerContent(content, contentText);
    const entryChanged = syncedEntryRef.current.id !== activeEntryId;
    const serverContentArrived = !syncedEntryRef.current.hasServerContent && nextHasServerContent;

    if (!entryChanged && !serverContentArrived) return;

    syncedEntryRef.current = {
      id: activeEntryId,
      hasServerContent: nextHasServerContent,
    };

    editor.commands.setContent(normalizeEditorContent(content, contentText), {
      emitUpdate: false,
    });
  }, [activeEntryId, content, contentText, editor]);

  useEffect(() => {
    const handleRetryEvent = (event: Event) => {
      const uploadId = (event as CustomEvent).detail?.uploadId;
      if (uploadId) {
        mediaUpload.retryUpload(uploadId);
      }
    };

    window.addEventListener("media-retry-upload", handleRetryEvent);
    return () => window.removeEventListener("media-retry-upload", handleRetryEvent);
  }, [mediaUpload]);

  return (
    <>
      <div className={fontClass}>
        <EditorContent editor={editor} />
      </div>

      {editor && <BubbleToolbar editor={editor} />}
      {editor && <FloatingToolbar editor={editor} onImageUpload={mediaUpload.triggerFilePicker} />}
    </>
  );
};

function hasServerContent(
  content: JournalEntryResponse["content"] | null | undefined,
  contentText?: string | null,
) {
  return Boolean(
    (content && Object.keys(content).length > 0) ||
    (typeof contentText === "string" && contentText.length > 0),
  );
}
