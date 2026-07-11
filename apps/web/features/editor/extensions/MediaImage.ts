import { Node, mergeAttributes } from "@tiptap/react";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { ReactNodeViewRenderer } from "@tiptap/react";
import { MediaImageView } from "../components/MediaImageView";
import { useUploadStore } from "../stores/useUploadStore";
import type { MediaMetadata, MediaResolver, MediaImageStorage } from "../types";

// Re-export for backward compatibility
export type { MediaMetadata, MediaResolver, MediaImageStorage };

export interface MediaImageOptions {
  HTMLAttributes: Record<string, unknown>;
}

const uploadTrackingPluginKey = new PluginKey("mediaImageUploadTracking");

/**
 * mediaImage — custom TipTap node for uploaded and external images.
 *
 * Persisted attributes: mediaId, src, alt, title
 * - mediaId: stable server ID for uploaded images
 * - src: URL for external images only
 * - Invariant: mediaId and src are mutually exclusive
 *
 * Upload state lives entirely in editor.storage and the UploadStore.
 * The position tracking plugin maintains uploadId → doc position mapping,
 * remapping on every transaction and auto-detecting node deletion/undo.
 *
 * When a node with a mediaId is deleted, onMediaDeleted is called for
 * backend cleanup.
 */
export const MediaImage = Node.create<MediaImageOptions, MediaImageStorage>({
  name: "mediaImage",
  group: "block",
  draggable: true,
  atom: true,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      mediaId: { default: null },
      src: { default: null },
      alt: { default: "" },
      title: { default: "" },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'img[data-type="mediaImage"]',
        getAttrs: (dom: HTMLElement) => {
          return {
            mediaId: dom.getAttribute("data-media-id"),
            src: dom.getAttribute("src"),
            alt: dom.getAttribute("alt") || "",
            title: dom.getAttribute("title") || "",
          };
        },
      },
    ];
  },

  renderHTML({ HTMLAttributes }: { HTMLAttributes: Record<string, unknown> }) {
    return [
      "img",
      mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {
        "data-type": "mediaImage",
        "data-media-id": HTMLAttributes.mediaId,
      }),
    ];
  },

  addStorage(): MediaImageStorage {
    return {
      resolver: null,
      uploadPositions: new Map<string, number>(),
      onMediaDeleted: null,
    };
  },

  addCommands() {
    return {
      insertMediaImage:
        (attrs: { mediaId?: string | null; src?: string | null; alt?: string; title?: string }) =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ({ commands }: any) => {
          return commands.insertContent({
            type: this.name,
            attrs,
          });
        },
    } as Record<string, unknown>;
  },

  addNodeView() {
    return ReactNodeViewRenderer(MediaImageView);
  },

  addProseMirrorPlugins() {
    const extensionStorage = (this.editor.storage as Record<string, unknown>)
      .mediaImage as MediaImageStorage;

    return [
      new Plugin({
        key: uploadTrackingPluginKey,

        appendTransaction(transactions, oldState, newState) {
          const uploadPositions = extensionStorage.uploadPositions;
          let hasChanges = false;
          for (const tr of transactions) {
            if (!tr.docChanged) continue;
            hasChanges = true;
          }
          if (!hasChanges) return null;

          // Track uploaded media nodes (with mediaId) that were deleted
          const oldMediaIds = new Set<string>();
          oldState.doc.descendants((node) => {
            if (node.type.name === "mediaImage" && node.attrs.mediaId) {
              oldMediaIds.add(node.attrs.mediaId);
            }
          });

          const newMediaIds = new Set<string>();
          newState.doc.descendants((node) => {
            if (node.type.name === "mediaImage" && node.attrs.mediaId) {
              newMediaIds.add(node.attrs.mediaId);
            }
          });

          // Find deleted media nodes and fire callback
          for (const mediaId of oldMediaIds) {
            if (!newMediaIds.has(mediaId) && extensionStorage.onMediaDeleted) {
              extensionStorage.onMediaDeleted(mediaId);
            }
          }

          // Handle upload position tracking (for placeholder nodes)
          if (uploadPositions.size === 0) return null;

          const toRemove: string[] = [];

          for (const [uploadId, oldPos] of uploadPositions.entries()) {
            let newPos = oldPos;
            for (const tr of transactions) {
              newPos = tr.mapping.map(newPos);
            }

            const node = newState.doc.nodeAt(newPos);
            if (node && node.type.name === "mediaImage" && node.attrs.mediaId === null) {
              uploadPositions.set(uploadId, newPos);
            } else {
              toRemove.push(uploadId);
            }
          }

          for (const uploadId of toRemove) {
            uploadPositions.delete(uploadId);
            useUploadStore.getState().cancelUpload(uploadId);
          }

          return null;
        },
      }),
    ];
  },
});
