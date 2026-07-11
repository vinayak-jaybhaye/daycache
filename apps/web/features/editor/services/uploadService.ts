/**
 * Upload service — network abstraction layer.
 *
 * Uses XMLHttpRequest for real upload progress events.
 * Supports abort via AbortSignal.
 */

export async function uploadFile(
  file: File,
  uploadUrl: string,
  signal: AbortSignal,
  onProgress?: (percent: number) => void,
): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open("PUT", uploadUrl, true);
    xhr.setRequestHeader("Content-Type", file.type);

    // Track upload progress
    if (onProgress) {
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          const percent = Math.round((event.loaded / event.total) * 100);
          onProgress(percent);
        }
      });
    }

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Upload failed: network error"));
    });

    xhr.addEventListener("abort", () => {
      const err = new Error("Upload aborted");
      err.name = "AbortError";
      reject(err);
    });

    // Wire AbortSignal to XHR
    if (signal.aborted) {
      xhr.abort();
      const err = new Error("Upload aborted");
      err.name = "AbortError";
      reject(err);
      return;
    }

    signal.addEventListener("abort", () => {
      xhr.abort();
    });

    xhr.send(file);
  });
}
