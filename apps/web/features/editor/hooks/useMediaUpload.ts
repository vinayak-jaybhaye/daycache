"use client";

import { useCallback, useEffect, useRef } from "react";
import type { Editor } from "@tiptap/react";
import { useUploadStore } from "../stores/useUploadStore";
import { uploadFile } from "../services/uploadService";
import { useJournalStore } from "@/store/useJournalStore";
import { entriesApi, type MediaResponse } from "@/lib/api/entries";
import type { MediaMetadata, MediaImageStorage } from "../types";

const IMAGE_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);

/**
 * Safely extract the typed MediaImageStorage from editor.storage.
 * TipTap's Storage type doesn't have an index signature, so we cast through `unknown`.
 */
function getMediaImageStorage(editor: Editor): MediaImageStorage | undefined {
  return (editor.storage as unknown as Record<string, unknown>).mediaImage as
    MediaImageStorage | undefined;
}

function isImageFile(file: File): boolean {
  return IMAGE_MIME_TYPES.has(file.type);
}

function extractImageFiles(fileList: FileList | null | undefined): File[] {
  if (!fileList) return [];
  return Array.from(fileList).filter(isImageFile);
}

/**
 * Maps a backend MediaStatusResponse to our internal MediaMetadata format.
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

/**
 * useMediaUpload — orchestrates file uploads for the editor.
 *
 * Handles:
 * - Multi-file upload from paste, drop, or file picker
 * - Placeholder node insertion with position tracking
 * - Background upload pipeline (ensureEntry → presign → PUT → confirm)
 * - Real upload progress via XHR
 * - Retry on failure
 * - Undo/delete safety via position tracking plugin
 * - Backend media cleanup when uploaded images are deleted from editor
 * - Blob URL lifecycle management
 * - AbortController cancellation
 */
export function useMediaUpload(editor: Editor | null) {
  const editorRef = useRef(editor);
  useEffect(() => {
    editorRef.current = editor;
  }, [editor]);

  // Run a single file through the upload pipeline
  const uploadSingleFile = useCallback(async (file: File, uploadId: string) => {
    const currentEditor = editorRef.current;
    if (!currentEditor) return;
    const journalStore = useJournalStore.getState();

    try {
      // 1. Ensure we have a persisted entry
      const entryId = await journalStore.ensureEntry();

      // 2. Request presigned upload URL
      const { upload_url, media_id } = await journalStore.requestMediaUpload(
        entryId,
        "image",
        file.type,
        file.name,
        file.size,
      );

      // Check if upload was cancelled (node deleted/undone)
      const uploadPositions = getMediaImageStorage(currentEditor)?.uploadPositions;
      if (!uploadPositions?.has(uploadId)) return;

      // 3. Upload file to presigned URL with progress tracking
      const abortController = useUploadStore.getState().getUpload(uploadId)?.abortController;
      if (!abortController) return;

      await uploadFile(file, upload_url, abortController.signal, (percent) => {
        useUploadStore.getState().setProgress(uploadId, percent);
      });

      // Check again after upload
      if (!uploadPositions?.has(uploadId)) return;

      // 4. Confirm upload with backend
      useUploadStore.getState().setConfirming(uploadId);
      const updatedEntry = await entriesApi.confirmMediaUpload(entryId, media_id);

      // Update the journal store with the new entry data
      useJournalStore.setState((state) => ({
        entries: { ...state.entries, [entryId]: updatedEntry },
      }));

      // 5. Push metadata into resolver cache immediately
      const resolver = getMediaImageStorage(currentEditor)?.resolver ?? null;
      if (resolver && updatedEntry.media) {
        const mediaItem = updatedEntry.media?.find((m: MediaResponse) => m.id === media_id);
        if (mediaItem) {
          resolver.updateCache(media_id, toMediaMetadata(mediaItem));
        }
      }

      // 6. Verify node still exists at tracked position before updating
      const currentPos = uploadPositions?.get(uploadId);
      if (currentPos === undefined) return;

      const node = currentEditor.view.state.doc.nodeAt(currentPos);
      if (!node || node.type.name !== "mediaImage" || node.attrs.mediaId !== null) {
        // Node was replaced or already updated
        useUploadStore.getState().completeUpload(uploadId, media_id);
        return;
      }

      // 7. Update node attrs: set mediaId, clear position tracking
      const tr = currentEditor.view.state.tr.setNodeMarkup(currentPos, null, {
        ...node.attrs,
        mediaId: media_id,
      });
      currentEditor.view.dispatch(tr);
      uploadPositions.delete(uploadId);

      // 8. Mark upload as complete (revokes blob URL)
      useUploadStore.getState().completeUpload(uploadId, media_id);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        // Upload was cancelled — already handled by cancelUpload
        return;
      }
      console.error("Upload failed:", err);
      useUploadStore
        .getState()
        .failUpload(uploadId, err instanceof Error ? err.message : "Upload failed");
    }
  }, []);

  // Retry a failed upload
  const retryUpload = useCallback(
    (uploadId: string) => {
      const currentEditor = editorRef.current;
      if (!currentEditor) return;

      const entry = useUploadStore.getState().getUpload(uploadId);
      if (!entry || entry.status !== "error" || !entry.file) return;

      const file = entry.file;
      const newController = useUploadStore.getState().retryUpload(uploadId);
      if (!newController) return;

      // Find the position of this upload in the tracking map
      // Re-run the upload pipeline
      uploadSingleFile(file, uploadId);
    },
    [uploadSingleFile],
  );

  // Upload multiple files, inserting all placeholders first to preserve order
  const uploadFiles = useCallback(
    (files: File[]) => {
      const currentEditor = editorRef.current;
      if (!currentEditor) return;

      const uploadPositions = getMediaImageStorage(currentEditor)?.uploadPositions;
      if (!uploadPositions) return;

      // Insert all placeholder nodes synchronously at the current cursor
      const insertions: Array<{ uploadId: string; pos: number; file: File }> = [];

      for (const file of files) {
        const uploadId = crypto.randomUUID();
        const blobUrl = URL.createObjectURL(file);

        // Start tracking in upload store (pass file for retry support)
        useUploadStore.getState().startUpload(uploadId, blobUrl, file);

        // Insert mediaImage placeholder node
        const { from } = currentEditor.state.selection;
        currentEditor
          .chain()
          .focus()
          .insertContentAt(from, {
            type: "mediaImage",
            attrs: { mediaId: null, src: null, alt: file.name, title: "" },
          })
          .run();

        // The node was inserted at `from`. Track its position.
        // After insertion, the node sits at `from`.
        uploadPositions.set(uploadId, from);
        insertions.push({ uploadId, pos: from, file });
      }

      // Start all uploads concurrently (non-blocking)
      for (const { uploadId, file } of insertions) {
        uploadSingleFile(file, uploadId);
      }
    },
    [uploadSingleFile],
  );

  // Paste handler for editorProps.handlePaste
  const handlePaste = useCallback(
    (_view: unknown, event: ClipboardEvent) => {
      const imageFiles = extractImageFiles(event.clipboardData?.files);
      if (imageFiles.length === 0) return false;

      event.preventDefault();
      uploadFiles(imageFiles);
      return true;
    },
    [uploadFiles],
  );

  // Drop handler for editorProps.handleDrop
  const handleDrop = useCallback(
    (_view: unknown, event: DragEvent, _slice: unknown, moved: boolean) => {
      if (moved) return false; // Internal drag — let TipTap handle it

      const imageFiles = extractImageFiles(event.dataTransfer?.files);
      if (imageFiles.length === 0) return false;

      event.preventDefault();
      uploadFiles(imageFiles);
      return true;
    },
    [uploadFiles],
  );

  // File picker trigger
  const triggerFilePicker = useCallback(() => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/gif,image/webp";
    input.multiple = true;
    input.onchange = () => {
      const files = extractImageFiles(input.files);
      if (files.length > 0) {
        uploadFiles(files);
      }
    };
    input.click();
  }, [uploadFiles]);

  // Wire up onMediaDeleted callback for backend cleanup
  useEffect(() => {
    const currentEditor = editorRef.current;
    if (!currentEditor) return;

    const storage = getMediaImageStorage(currentEditor);
    if (!storage) return;

    storage.onMediaDeleted = (mediaId: string) => {
      const { activeEntryId } = useJournalStore.getState();
      if (!activeEntryId || activeEntryId === "new") return;

      // Fire-and-forget backend cleanup
      entriesApi.deleteMedia(activeEntryId, mediaId).catch((err: unknown) => {
        console.error("Failed to remove media from backend:", err);
      });
    };

    return () => {
      if (storage) {
        storage.onMediaDeleted = null;
      }
    };
  }, [editor]);

  // Cleanup on unmount — cancel all active uploads
  useEffect(() => {
    return () => {
      useUploadStore.getState().cleanup();
    };
  }, []);

  return {
    uploadFiles,
    handlePaste,
    handleDrop,
    triggerFilePicker,
    retryUpload,
  };
}
