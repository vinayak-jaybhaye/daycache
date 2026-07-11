/* eslint-disable @next/next/no-img-element */
"use client";

import React from "react";
import { NodeViewWrapper } from "@tiptap/react";
import type { ReactNodeViewProps } from "@tiptap/react";
import { useUploadStore } from "../stores/useUploadStore";
import type { MediaMetadata, MediaImageStorage } from "../extensions/MediaImage";
import { ImageOff, RotateCcw, Trash2, Loader2 } from "lucide-react";

/**
 * MediaImageView — React NodeView for the mediaImage node.
 *
 * Rendering logic:
 * 1. Check for active upload at this position (via UploadStore)
 * 2. If mediaId → resolve via MediaResolver (editor.storage)
 * 3. If src → render external URL
 * 4. Otherwise → broken placeholder
 */
export const MediaImageView: React.FC<ReactNodeViewProps> = ({
  node,
  editor,
  getPos,
  deleteNode,
}) => {
  const { mediaId, src, alt, title } = node.attrs;
  const [showOverlay, setShowOverlay] = React.useState(false);

  // Find if there's an active upload at this node's position
  const uploadPositions = (
    (editor.storage as Record<string, unknown>).mediaImage as MediaImageStorage | undefined
  )?.uploadPositions;
  const uploads = useUploadStore((state) => state.uploads);

  let activeUploadId: string | null = null;
  if (uploadPositions) {
    const pos = typeof getPos === "function" ? getPos() : undefined;
    if (pos !== undefined) {
      for (const [uid, uPos] of uploadPositions.entries()) {
        if (uPos === pos) {
          activeUploadId = uid;
          break;
        }
      }
    }
  }

  const activeUpload = activeUploadId ? uploads[activeUploadId] : null;

  // Resolve media metadata from resolver
  const resolver =
    ((editor.storage as Record<string, unknown>).mediaImage as MediaImageStorage | undefined)
      ?.resolver ?? null;
  const [resolved, setResolved] = React.useState<MediaMetadata | null>(null);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  React.useEffect(() => {
    if (mediaId && resolver) {
      const meta = resolver.resolve(mediaId);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResolved(meta);
    } else {
      setResolved(null);
    }
  }, [mediaId, resolver, uploads]); // re-check when uploads change (cache may have updated)

  // Poll if processing
  React.useEffect(() => {
    if (
      !mediaId ||
      !resolver ||
      !resolved ||
      (resolved.status !== "pending" && resolved.status !== "processing")
    ) {
      return;
    }

    const interval = setInterval(async () => {
      const meta = await resolver.refresh(mediaId);
      if (meta) {
        setResolved(meta);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [mediaId, resolver, resolved, resolved?.status]);

  const handleRefresh = React.useCallback(async () => {
    if (!mediaId || !resolver) return;
    setIsRefreshing(true);
    try {
      const meta = await resolver.refresh(mediaId);
      setResolved(meta);
    } finally {
      setIsRefreshing(false);
    }
  }, [mediaId, resolver]);

  const handleRemove = React.useCallback(() => {
    if (activeUploadId) {
      useUploadStore.getState().removeUpload(activeUploadId);
    }
    deleteNode();
  }, [activeUploadId, deleteNode]);

  const handleRetry = React.useCallback(() => {
    if (!activeUploadId) return;
    // Trigger retry — the useMediaUpload hook exposes retryUpload
    // We dispatch a custom event that EditorView listens to
    window.dispatchEvent(
      new CustomEvent("media-retry-upload", { detail: { uploadId: activeUploadId } }),
    );
  }, [activeUploadId]);

  const handleDeleteUploaded = React.useCallback(() => {
    if (!mediaId) return;
    // The MediaImage extension's appendTransaction will detect the deletion
    // and fire onMediaDeleted for backend cleanup
    deleteNode();
  }, [mediaId, deleteNode]);

  // 1. Active upload in progress
  if (activeUpload) {
    if (activeUpload.status === "error") {
      return (
        <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
          <div className="media-image-error">
            <ImageOff size={24} />
            <span className="media-image-error-text">
              Upload failed: {activeUpload.error || "Unknown error"}
            </span>
            <div className="media-image-error-actions">
              {activeUpload.file && (
                <button onClick={handleRetry} className="media-image-btn">
                  <RotateCcw size={14} /> Retry
                </button>
              )}
              <button onClick={handleRemove} className="media-image-btn media-image-btn-danger">
                <Trash2 size={14} /> Remove
              </button>
            </div>
          </div>
        </NodeViewWrapper>
      );
    }

    // Uploading or confirming
    return (
      <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
        <div className="media-image-uploading">
          <img
            src={activeUpload.blobUrl}
            alt={alt || "Uploading..."}
            className="media-image-preview"
          />
          <div className="media-image-overlay">
            <div className="media-image-progress-ring">
              <svg viewBox="0 0 36 36" className="media-image-progress-svg">
                <path
                  className="media-image-progress-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="media-image-progress-fill"
                  strokeDasharray={`${activeUpload.progress}, 100`}
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="media-image-progress-text">
                {activeUpload.status === "confirming"
                  ? "Processing..."
                  : `${activeUpload.progress}%`}
              </span>
            </div>
          </div>
        </div>
      </NodeViewWrapper>
    );
  }

  // 2. Has mediaId → resolve from MediaResolver
  if (mediaId) {
    if (isRefreshing) {
      return (
        <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
          <div className="media-image-loading">
            <Loader2 size={24} className="animate-spin" />
            <span>Loading image...</span>
          </div>
        </NodeViewWrapper>
      );
    }

    if (!resolved || resolved.status === "not_found") {
      return (
        <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
          <div className="media-image-error">
            <ImageOff size={24} />
            <span className="media-image-error-text">Image unavailable</span>
            <div className="media-image-error-actions">
              <button onClick={handleRefresh} className="media-image-btn">
                <RotateCcw size={14} /> Retry
              </button>
              <button onClick={handleRemove} className="media-image-btn media-image-btn-danger">
                <Trash2 size={14} /> Remove
              </button>
            </div>
          </div>
        </NodeViewWrapper>
      );
    }

    if (resolved.status === "failed") {
      return (
        <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
          <div className="media-image-error">
            <ImageOff size={24} />
            <span className="media-image-error-text">Image processing failed</span>
            <div className="media-image-error-actions">
              <button onClick={handleRemove} className="media-image-btn media-image-btn-danger">
                <Trash2 size={14} /> Remove
              </button>
            </div>
          </div>
        </NodeViewWrapper>
      );
    }

    if (resolved.readUrl) {
      return (
        <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
          <div
            className="media-image-completed-wrapper"
            onMouseEnter={() => setShowOverlay(true)}
            onMouseLeave={() => setShowOverlay(false)}
          >
            <img
              src={resolved.readUrl}
              alt={alt || resolved.altText || ""}
              title={title || ""}
              className="media-image-rendered"
            />
            {showOverlay && (
              <div className="media-image-hover-toolbar">
                <button
                  onClick={handleDeleteUploaded}
                  className="media-image-btn media-image-btn-danger"
                  title="Delete image"
                >
                  <Trash2 size={14} /> Delete
                </button>
              </div>
            )}
          </div>
        </NodeViewWrapper>
      );
    }

    // Has metadata but no readUrl yet (still processing) — show blurhash or placeholder
    return (
      <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
        <div className="media-image-processing">
          {resolved.blurhash ? (
            <div
              className="media-image-blurhash"
              style={{
                width: resolved.width || 400,
                height: resolved.height || 300,
                background: `var(--border-soft)`,
              }}
            />
          ) : (
            <div className="media-image-loading">
              <Loader2 size={24} className="animate-spin" />
              <span>Processing image...</span>
            </div>
          )}
        </div>
      </NodeViewWrapper>
    );
  }

  // 3. Has src (external URL)
  if (src) {
    return (
      <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
        <img src={src} alt={alt || ""} title={title || ""} className="media-image-rendered" />
      </NodeViewWrapper>
    );
  }

  // 4. No mediaId, no src, no active upload → broken placeholder
  return (
    <NodeViewWrapper data-type="mediaImage" className="media-image-wrapper">
      <div className="media-image-error">
        <ImageOff size={24} />
        <span className="media-image-error-text">No image</span>
        <div className="media-image-error-actions">
          <button onClick={handleRemove} className="media-image-btn media-image-btn-danger">
            <Trash2 size={14} /> Remove
          </button>
        </div>
      </div>
    </NodeViewWrapper>
  );
};
