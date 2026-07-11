/**
 * Utility functions for media handling.
 */

/**
 * Supported image MIME types for upload.
 */
const IMAGE_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "image/svg+xml",
]);

/**
 * Maximum file size for images: 50MB
 */
export const MAX_IMAGE_SIZE_BYTES = 50 * 1024 * 1024;

/**
 * Check if a file is a supported image type.
 */
export function isImageFile(file: File): boolean {
  return IMAGE_MIME_TYPES.has(file.type) && file.size > 0 && file.size <= MAX_IMAGE_SIZE_BYTES;
}

/**
 * Check if a file size is within limits.
 */
export function isFileSizeValid(file: File): boolean {
  return file.size > 0 && file.size <= MAX_IMAGE_SIZE_BYTES;
}

/**
 * Extract image files from a FileList.
 * Filters by MIME type and size.
 */
export function extractImageFiles(fileList: FileList | null | undefined): File[] {
  if (!fileList) return [];
  return Array.from(fileList).filter(isImageFile);
}

/**
 * Get human-readable file size (e.g., "2.5 MB").
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

/**
 * Generate a unique upload ID for tracking.
 */
export function generateUploadId(): string {
  return crypto.randomUUID();
}

/**
 * Create a blob URL from a file.
 * Remember to revoke it when done: URL.revokeObjectURL(blobUrl)
 */
export function createBlobUrl(file: File): string {
  return URL.createObjectURL(file);
}

/**
 * Check if a URL is a blob URL.
 */
export function isBlobUrl(url: string | null | undefined): boolean {
  return url?.startsWith("blob:") ?? false;
}

/**
 * Check if a URL is a signed upload URL.
 */
export function isSignedUrl(url: string | null | undefined): boolean {
  return (
    (url?.includes("?") && (url?.includes("X-Amz-Signature") || url?.includes("Signature"))) ??
    false
  );
}

/**
 * Extract filename from a File.
 */
export function getFileName(file: File): string {
  return file.name || "image";
}

/**
 * Extract file extension.
 */
export function getFileExtension(file: File): string {
  return file.name.split(".").pop() || "";
}

/**
 * Convert MIME type to file extension.
 */
export function mimeToExtension(mimeType: string): string {
  const map: Record<string, string> = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
  };
  return map[mimeType] || "";
}

/**
 * Validate image dimensions.
 * Returns { valid: boolean, width?: number, height?: number, error?: string }
 */
export async function validateImageDimensions(
  file: File,
  options?: {
    minWidth?: number;
    maxWidth?: number;
    minHeight?: number;
    maxHeight?: number;
  },
): Promise<{
  valid: boolean;
  width?: number;
  height?: number;
  error?: string;
}> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";

    img.onload = () => {
      const { minWidth, maxWidth, minHeight, maxHeight } = options || {};

      if (minWidth && img.width < minWidth) {
        return resolve({
          valid: false,
          width: img.width,
          height: img.height,
          error: `Image width must be at least ${minWidth}px`,
        });
      }

      if (maxWidth && img.width > maxWidth) {
        return resolve({
          valid: false,
          width: img.width,
          height: img.height,
          error: `Image width must be at most ${maxWidth}px`,
        });
      }

      if (minHeight && img.height < minHeight) {
        return resolve({
          valid: false,
          width: img.width,
          height: img.height,
          error: `Image height must be at least ${minHeight}px`,
        });
      }

      if (maxHeight && img.height > maxHeight) {
        return resolve({
          valid: false,
          width: img.width,
          height: img.height,
          error: `Image height must be at most ${maxHeight}px`,
        });
      }

      resolve({ valid: true, width: img.width, height: img.height });
    };

    img.onerror = () => {
      resolve({ valid: false, error: "Failed to load image" });
    };

    img.src = createBlobUrl(file);
  });
}

/**
 * Create error message for file validation failures.
 */
export function createFileErrorMessage(file: File): string {
  if (!isImageFile(file)) {
    if (!IMAGE_MIME_TYPES.has(file.type)) {
      return `Unsupported format: ${file.type}. Please use JPEG, PNG, GIF, or WebP.`;
    }

    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      return `File too large: ${formatFileSize(file.size)}. Maximum is ${formatFileSize(MAX_IMAGE_SIZE_BYTES)}.`;
    }

    return "Invalid image file";
  }

  return "";
}
