"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Trash2, Smile, MoreVertical, Cloud, Loader2 } from "lucide-react";
import { useJournalStore } from "@/store/useJournalStore";
import { useUserStore } from "@/store/useUserStore";
import { EditorContent } from "@tiptap/react";
import { entriesApi, type MediaResponse } from "@/lib/api/entries";
import { EditorProperties } from "./components/EditorProperties";
import type { MediaResolver, MediaMetadata } from "./types";
import { BubbleToolbar } from "./components/BubbleToolbar";
import { FloatingToolbar } from "./components/toolbars/FloatingToolbar";
import { useMediaUpload } from "./hooks/useMediaUpload";
import { useAutoSave } from "./hooks/useAutoSave";
import { useEditorCore } from "./hooks/useEditorCore";
import { useEditorShortcuts } from "./hooks/useEditorShortcuts";
import { EditorService } from "./services/editorService";
import { useOnClickOutside } from "@/hooks/useOnClickOutside";

/**
 * Maps a backend MediaStatusResponse to our internal MediaMetadata.
 */
function toMediaMetadata(m: MediaResponse): MediaMetadata {
  let status: MediaMetadata["status"] = "completed";
  if (m.processing_status === "pending") status = "pending";
  else if (m.processing_status === "processing") status = "processing";
  else if (m.processing_status === "failed") status = "failed";
  else if (m.upload_status === "pending") status = "pending";

  return {
    readUrl: m.read_url ?? null,
    thumbnailUrl: m.thumbnail_url ?? null,
    blurhash: m.blurhash ?? null,
    width: m.width ?? null,
    height: m.height ?? null,
    altText: m.alt_text ?? null,
    status,
  };
}

export const EditorView = () => {
  const { entries, activeEntryId, setActiveEntry, deleteEntry } = useJournalStore();
  const { settings } = useUserStore();

  const entry = activeEntryId && activeEntryId !== "new" ? entries[activeEntryId] : null;
  const entryDate = entry?.date ? new Date(entry.date + "T12:00:00Z") : new Date();

  const [title, setTitle] = useState(entry?.title || "");
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useOnClickOutside(menuRef, () => {
    if (isMenuOpen) setIsMenuOpen(false);
  });

  // Font class from user settings
  const fontClass = useMemo(() => {
    const f = (settings as { editor_font?: string })?.editor_font;
    if (f === "Inter") return "font-sans";
    if (f === "Caveat") return "font-hand";
    return "font-serif";
  }, [settings]);

  // Media resolver — backed by entry.media[] cache
  const mediaCacheRef = useRef(new Map<string, MediaMetadata>());

  useEffect(() => {
    mediaCacheRef.current.clear();
    for (const m of entry?.media ?? []) {
      mediaCacheRef.current.set(m.id, toMediaMetadata(m));
    }
  }, [entry?.media]);

  const resolver: MediaResolver = useMemo(
    () => ({
      resolve: (mediaId: string) => mediaCacheRef.current.get(mediaId) ?? null,

      refresh: async (mediaId: string) => {
        if (!activeEntryId || activeEntryId === "new") return null;
        try {
          const freshEntry = await entriesApi.get(activeEntryId);
          const m = freshEntry.media?.find((m: MediaResponse) => m.id === mediaId);
          if (!m) return null;
          const meta = toMediaMetadata(m);
          mediaCacheRef.current.set(mediaId, meta);
          return meta;
        } catch {
          return null;
        }
      },

      updateCache: (mediaId: string, meta: MediaMetadata) => {
        mediaCacheRef.current.set(mediaId, meta);
      },
    }),
    [activeEntryId],
  );

  // Ref for media upload hook
  const mediaUploadRef = useRef<ReturnType<typeof useMediaUpload> | null>(null);

  // Parse content safely
  const getEditorContent = () => {
    if (!entry?.content) return "";

    try {
      if (typeof entry.content === "string") {
        const parsed = JSON.parse(entry.content);
        if (parsed && typeof parsed === "object" && parsed.type === "doc") {
          return parsed;
        }
        return entry.content;
      } else if (
        typeof entry.content === "object" &&
        (entry.content as Record<string, unknown>).type === "doc"
      ) {
        return entry.content;
      }
    } catch {
      // Fall back to content_text
    }

    return entry.content_text || "";
  };

  // Create editor with refactored hook
  const editor = useEditorCore({
    content: getEditorContent(),
    fontClass,
    placeholder: "Start writing... Type '/' for commands",
    mediaResolver: resolver,
    onImageUpload: () => mediaUploadRef.current?.triggerFilePicker(),
    handlePaste: (view: unknown, event: ClipboardEvent) =>
      mediaUploadRef.current?.handlePaste(view, event) ?? false,
    handleDrop: (view: unknown, event: DragEvent, slice: unknown, moved: boolean) =>
      mediaUploadRef.current?.handleDrop(view, event, slice, moved) ?? false,
  });

  // Register keyboard shortcuts
  useEditorShortcuts(editor, {
    enableMarkdownShortcuts: true,
    enableCommandShortcuts: true,
    onImageUploadShortcut: () => mediaUploadRef.current?.triggerFilePicker(),
  });

  // Create media upload hook
  const mediaUpload = useMediaUpload(editor);
  useEffect(() => {
    mediaUploadRef.current = mediaUpload;
  }, [mediaUpload]);

  // Sync content when entry changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTitle(entry?.title || "");

    if (editor && !editor.isDestroyed) {
      let newContent: string | Record<string, unknown> = "";
      try {
        if (typeof entry?.content === "string") {
          newContent = JSON.parse(entry.content);
        } else if (entry?.content) {
          newContent = entry.content;
        }
      } catch {
        newContent = "";
      }

      const newText = entry?.content_text || "";
      const currentJSON = editor.getJSON();

      if (JSON.stringify(currentJSON) !== JSON.stringify(newContent)) {
        const isValidDoc =
          newContent &&
          typeof newContent === "object" &&
          (newContent as Record<string, unknown>).type === "doc";
        const contentToSet = isValidDoc
          ? newContent
          : (newContent as { text?: string })?.text || newText || "";
        setTimeout(() => {
          EditorService.setContent(editor, contentToSet);
        }, 0);
      }
    }
  }, [entry?.id, entry?.title, entry?.content, entry?.content_text, editor]);

  // Auto-save
  const { isSaving } = useAutoSave(editor, title, activeEntryId);

  // Listen for retry events from MediaImageView
  useEffect(() => {
    const handleRetryEvent = (e: Event) => {
      const uploadId = (e as CustomEvent).detail?.uploadId;
      if (uploadId) {
        mediaUpload.retryUpload(uploadId);
      }
    };
    window.addEventListener("media-retry-upload", handleRetryEvent);
    return () => window.removeEventListener("media-retry-upload", handleRetryEvent);
  }, [mediaUpload]);

  // Delete handler
  const handleDelete = useCallback(async () => {
    if (!entry) return;
    if (confirm("Are you sure you want to delete this entry?")) {
      await deleteEntry(entry.id);
      setActiveEntry(null);
    }
  }, [entry, deleteEntry, setActiveEntry]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className="hide-scrollbar absolute inset-0 z-50 min-h-screen w-full overflow-y-auto bg-[var(--bg-color)] px-4 pt-20 pb-24 sm:px-6 sm:pt-24 sm:pb-32 md:px-12"
    >
      {/* Header */}
      <div className="pointer-events-none fixed top-4 right-4 left-4 z-50 flex items-center justify-between sm:top-8 sm:right-8 sm:left-8"></div>

      {/* Content */}
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-8 flex flex-wrap items-center gap-2 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase sm:mb-12 sm:gap-4">
          <span className="flex items-center gap-2">
            {new Intl.DateTimeFormat("en-US", {
              month: "long",
              day: "numeric",
              year: "numeric",
            }).format(entryDate)}
          </span>
          {/* TODO: Add location */}
          {/* <span className="flex items-center gap-2">
            <MapPin size={14} /> {entry?.location || "Current Location"}
          </span> */}
          <span className="flex items-center gap-2">
            <Smile size={14} /> Reflective
          </span>

          <div className="flex flex-1 items-center justify-end gap-1">
            <div
              className="flex h-8 w-8 items-center justify-center text-[var(--text-muted)]"
              title={isSaving ? "Saving..." : "Saved to Cloud"}
            >
              {isSaving ? (
                <Loader2 size={16} className="animate-spin text-[var(--accent-color)]" />
              ) : (
                <Cloud size={16} className="text-[var(--text-muted)]" />
              )}
            </div>

            {entry && (
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setIsMenuOpen(!isMenuOpen)}
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-[var(--ink-color)] transition-colors hover:bg-[var(--border-soft)] ${isMenuOpen ? "bg-[var(--border-soft)]" : ""}`}
                >
                  <MoreVertical size={16} />
                </button>

                {isMenuOpen && (
                  <div className="absolute top-full right-0 z-50 mt-2 w-64 rounded-xl border border-[var(--border-soft)] bg-[var(--card-bg)] p-2 shadow-xl backdrop-blur-md">
                    <div className="mb-2 border-b border-[var(--border-soft)] px-3 pt-2 pb-2">
                      <p className="font-sans text-[10px] tracking-widest text-[var(--text-muted)] uppercase">
                        Entry Details
                      </p>
                      <div className="mt-2 space-y-1 font-serif text-sm text-[var(--ink-color)] lowercase normal-case">
                        <p className="flex justify-between">
                          <span className="text-[var(--text-muted)]">Words:</span>
                          <span>{entry.word_count || 0}</span>
                        </p>
                        <p className="flex justify-between">
                          <span className="text-[var(--text-muted)]">Created:</span>
                          <span>
                            {new Intl.DateTimeFormat("en-US", {
                              dateStyle: "short",
                              timeStyle: "short",
                            }).format(new Date(entry.created_at))}
                          </span>
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setIsMenuOpen(false);
                        handleDelete();
                      }}
                      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left font-serif text-sm text-red-500 normal-case transition-colors hover:bg-red-500/10 dark:text-red-400"
                    >
                      <Trash2 size={16} /> Delete Entry
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Title Input */}
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Entry title"
          className={`mb-4 w-full border-none bg-transparent font-serif text-3xl text-[var(--ink-color)] outline-none placeholder:text-[var(--text-muted)] placeholder:opacity-50 sm:mb-6 sm:text-4xl md:text-5xl`}
        />

        {/* Notion-style Properties */}
        {entry && activeEntryId && activeEntryId !== "new" && (
          <EditorProperties entryId={activeEntryId} />
        )}

        {/* Editor Context Provider */}
        <EditorContent editor={editor} />

        {editor && <BubbleToolbar editor={editor} />}
      </div>

      {editor && <FloatingToolbar editor={editor} onImageUpload={mediaUpload.triggerFilePicker} />}
    </motion.div>
  );
};
