/**
 * Central type definitions for the editor system.
 * All editor types are exported from this single source of truth.
 */

import type { ReactNode } from "react";
import type { Editor } from "@tiptap/core";

/**
 * MediaMetadata — resolved metadata for a media asset.
 * Returned by MediaResolver.resolve() when rendering nodes.
 */
export interface MediaMetadata {
  readUrl: string | null;
  thumbnailUrl: string | null;
  blurhash: string | null;
  width: number | null;
  height: number | null;
  altText: string | null;
  status: "pending" | "processing" | "completed" | "failed" | "not_found";
}

/**
 * MediaResolver — interface for resolving mediaId to current metadata.
 * Implemented by EditorView to look up media from entry.media[] cache.
 */
export interface MediaResolver {
  /** Synchronously resolve mediaId to metadata. */
  resolve: (mediaId: string) => MediaMetadata | null;

  /** Refresh metadata from backend. */
  refresh: (mediaId: string) => Promise<MediaMetadata | null>;

  /** Update resolver's internal cache (called after upload completes). */
  updateCache: (mediaId: string, metadata: MediaMetadata) => void;
}

/**
 * MediaImageStorage — storage interface for MediaImage node.
 * Contains resolver, upload tracking, and deletion callbacks.
 */
export interface MediaImageStorage {
  resolver: MediaResolver | null;
  uploadPositions: Map<string, number>;
  onMediaDeleted: ((mediaId: string) => void) | null;
}

/**
 * SlashCommand — a single command in the slash menu.
 * Searchable, groupable, with keyboard shortcuts.
 */
export type SlashGroup = "basic" | "lists" | "media" | "blocks" | "ai";

export interface SlashCommand {
  id: string;
  title: string;
  description?: string;
  icon: ReactNode;
  group: SlashGroup;
  aliases: string[];
  keywords: string[];
  shortcut?: string;
  priority: number;
  isVisible: (editor: Editor) => boolean;
  isEnabled: (editor: Editor) => boolean;
  run: (ctx: SlashCommandContext) => void | Promise<void>;
}

export interface SlashCommandContext {
  editor: Editor;
  triggerImageUpload: () => void;
}

/**
 * EditorUIState — tracks editor UI/focus state.
 * Separate from document content and upload state.
 */
export interface EditorUIState {
  isFocused: boolean;
  editMode: "edit" | "view";
  selectedText: string;
  cursorPos: number;
}

/**
 * UploadEntry — represents a single file upload in progress.
 */
export interface UploadEntry {
  uploadId: string;
  blobUrl: string;
  progress: number;
  status: "uploading" | "confirming" | "done" | "error" | "cancelled";
  error?: string;
  mediaId?: string;
  abortController: AbortController;
  file?: File; // Retained for retry support
}

/**
 * EditorConfiguration — options for editor initialization.
 */
export interface EditorConfig {
  placeholder?: string;
  editable?: boolean;
  extensions?: import("@tiptap/core").Extension[];
  attributes?: Record<string, string>;
}

/**
 * Branded types for better type safety.
 */
export type UploadId = string & { readonly __brand: "UploadId" };
export type MediaId = string & { readonly __brand: "MediaId" };
export type EntryId = string & { readonly __brand: "EntryId" };
