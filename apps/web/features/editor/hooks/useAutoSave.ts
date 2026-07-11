"use client";

import { useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import { useJournalStore } from "@/store/useJournalStore";

/**
 * Recursively scans a TipTap document JSON to extract all mediaImage
 * nodes with a mediaId attribute, returning a list of media IDs.
 */
function extractMediaIds(doc: Record<string, unknown>): string[] {
  const ids: string[] = [];

  function walk(node: Record<string, unknown> | null | undefined) {
    if (!node) return;
    if (node.type === "mediaImage") {
      const attrs = node.attrs as Record<string, unknown> | undefined;
      if (attrs?.mediaId) {
        ids.push(attrs.mediaId as string);
      }
    }
    if (Array.isArray(node.content)) {
      for (const child of node.content as Array<Record<string, unknown>>) {
        walk(child);
      }
    }
  }

  walk(doc);
  return ids;
}

/**
 * useAutoSave — debounced auto-save for the editor.
 *
 * Handles both new entry creation and existing entry updates.
 * Compares title + content JSON against last-saved values to avoid no-op saves.
 * Sends media_ids extracted from the document for backend reconciliation.
 * The document JSON is always clean — no upload state leaks into saved content.
 */
export function useAutoSave(editor: Editor | null, title: string, activeEntryId: string | null) {
  const [isSaving, setIsSaving] = useState(false);
  const lastSavedRef = useRef<{ title: string; content: string }>({
    title: "",
    content: "",
  });

  const isSavingRef = useRef(false);
  const pendingSaveRef = useRef(false);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;

    const triggerSave = async () => {
      const contentJSON = editor.getJSON();
      const contentText = editor.getText();
      const contentStr = JSON.stringify(contentJSON);

      // Don't auto-save completely empty new entries
      if (!title && !contentText && activeEntryId === "new") return;

      // Check if anything actually changed
      if (title === lastSavedRef.current.title && contentStr === lastSavedRef.current.content) {
        return;
      }

      if (isSavingRef.current) {
        pendingSaveRef.current = true;
        return;
      }

      setIsSaving(true);
      isSavingRef.current = true;
      pendingSaveRef.current = false;
      const { createEntry, updateEntry, entries } = useJournalStore.getState();

      // Extract media_ids from the document for backend reconciliation
      const mediaIds = extractMediaIds(contentJSON);

      try {
        if (activeEntryId === "new") {
          await createEntry({
            title,
            content: contentJSON, // Send as JSON object
          });
          lastSavedRef.current = { title, content: contentStr };
        } else if (activeEntryId) {
          const existingEntry = entries[activeEntryId];
          if (existingEntry) {
            await updateEntry(activeEntryId, {
              title,
              content: contentJSON, // Send as JSON object
              media_ids: mediaIds,
            });
            lastSavedRef.current = { title, content: contentStr };
          }
        }
      } catch (err) {
        console.error("Auto-save failed:", err);
      } finally {
        setIsSaving(false);
        isSavingRef.current = false;

        // If another save was queued while we were saving, trigger it now
        if (pendingSaveRef.current) {
          debouncedSave();
        }
      }
    };

    let handler: NodeJS.Timeout;

    const debouncedSave = () => {
      clearTimeout(handler);
      handler = setTimeout(triggerSave, 1000);
    };

    // Trigger on title or activeEntryId change
    debouncedSave();

    // Trigger on editor content update
    editor.on("update", debouncedSave);

    return () => {
      clearTimeout(handler);
      editor.off("update", debouncedSave);
    };
  }, [editor, title, activeEntryId]);

  // Reset last-saved state when entry changes
  useEffect(() => {
    if (activeEntryId && activeEntryId !== "new") {
      const entry = useJournalStore.getState().entries[activeEntryId];
      if (entry) {
        lastSavedRef.current = {
          title: entry.title || "",
          content: JSON.stringify(entry.content || {}),
        };
      }
    } else {
      lastSavedRef.current = { title: "", content: "" };
    }
  }, [activeEntryId]);

  return { isSaving };
}
