/**
 * Configuration constants for the editor.
 */

/** Auto-save debounce delay in milliseconds */
export const AUTO_SAVE_DELAY_MS = 1000;

/** Upload progress update interval */
export const UPLOAD_PROGRESS_UPDATE_MS = 100;

/** Retry upload delay in milliseconds */
export const RETRY_UPLOAD_DELAY_MS = 500;

/** Maximum number of retry attempts for uploads */
export const MAX_UPLOAD_RETRIES = 3;

/** Maximum file size for images: 50MB */
export const MAX_FILE_SIZE = 50 * 1024 * 1024;

/** Default editor placeholder text */
export const DEFAULT_PLACEHOLDER = "Start writing... Type '/' for commands";

/** Slash command menu trigger character */
export const SLASH_COMMAND_CHAR = "/";

/** Supported image MIME types */
export const IMAGE_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/svg+xml",
];

/** CSS class for editor wrapper */
export const EDITOR_CLASS = "tiptap-editor";

/** CSS class for bubble toolbar */
export const BUBBLE_TOOLBAR_CLASS = "tiptap-bubble-toolbar";

/** CSS class for floating toolbar */
export const FLOATING_TOOLBAR_CLASS = "tiptap-floating-toolbar";

/** CSS class for slash command menu */
export const SLASH_MENU_CLASS = "tiptap-slash-menu";

/** Upload storage duration before cleanup (in ms) */
export const UPLOAD_CLEANUP_DELAY_MS = 5 * 60 * 1000; // 5 minutes

/** Animation duration for media upload progress */
export const MEDIA_UPLOAD_ANIMATION_MS = 300;

/** z-index for editor UI overlays */
export const EDITOR_Z_INDEX_BASE = 40;
export const BUBBLE_TOOLBAR_Z_INDEX = 50;
export const FLOATING_TOOLBAR_Z_INDEX = 45;
export const SLASH_MENU_Z_INDEX = 55;
