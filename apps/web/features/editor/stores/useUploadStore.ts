import { create } from "zustand";

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

interface UploadStoreState {
  uploads: Record<string, UploadEntry>;

  startUpload: (uploadId: string, blobUrl: string, file?: File) => AbortController;
  setProgress: (uploadId: string, progress: number) => void;
  setConfirming: (uploadId: string) => void;
  completeUpload: (uploadId: string, mediaId: string) => void;
  failUpload: (uploadId: string, error: string) => void;
  cancelUpload: (uploadId: string) => void;
  removeUpload: (uploadId: string) => void;
  retryUpload: (uploadId: string) => AbortController | null;
  cleanup: () => void;
  getUpload: (uploadId: string) => UploadEntry | undefined;
}

export const useUploadStore = create<UploadStoreState>((set, get) => ({
  uploads: {},

  startUpload: (uploadId, blobUrl, file) => {
    const abortController = new AbortController();
    set((state) => ({
      uploads: {
        ...state.uploads,
        [uploadId]: {
          uploadId,
          blobUrl,
          progress: 0,
          status: "uploading",
          abortController,
          file,
        },
      },
    }));
    return abortController;
  },

  setProgress: (uploadId, progress) => {
    set((state) => {
      const entry = state.uploads[uploadId];
      if (!entry || entry.status !== "uploading") return state;
      return {
        uploads: {
          ...state.uploads,
          [uploadId]: { ...entry, progress },
        },
      };
    });
  },

  setConfirming: (uploadId) => {
    set((state) => {
      const entry = state.uploads[uploadId];
      if (!entry) return state;
      return {
        uploads: {
          ...state.uploads,
          [uploadId]: { ...entry, status: "confirming", progress: 100 },
        },
      };
    });
  },

  completeUpload: (uploadId, mediaId) => {
    const entry = get().uploads[uploadId];
    if (entry) {
      URL.revokeObjectURL(entry.blobUrl);
    }
    set((state) => {
      const entry = state.uploads[uploadId];
      if (!entry) return state;
      return {
        uploads: {
          ...state.uploads,
          [uploadId]: { ...entry, status: "done", mediaId, file: undefined },
        },
      };
    });
  },

  failUpload: (uploadId, error) => {
    // Don't revoke blob URL on failure — we need it for retry preview
    set((state) => {
      const entry = state.uploads[uploadId];
      if (!entry) return state;
      return {
        uploads: {
          ...state.uploads,
          [uploadId]: { ...entry, status: "error", error },
        },
      };
    });
  },

  cancelUpload: (uploadId) => {
    const entry = get().uploads[uploadId];
    if (entry) {
      entry.abortController.abort();
      URL.revokeObjectURL(entry.blobUrl);
    }
    set((state) => {
      const newUploads = { ...state.uploads };
      delete newUploads[uploadId];
      return { uploads: newUploads };
    });
  },

  removeUpload: (uploadId) => {
    const entry = get().uploads[uploadId];
    if (entry) {
      if (entry.status === "uploading" || entry.status === "confirming") {
        entry.abortController.abort();
      }
      URL.revokeObjectURL(entry.blobUrl);
    }
    set((state) => {
      const newUploads = { ...state.uploads };
      delete newUploads[uploadId];
      return { uploads: newUploads };
    });
  },

  retryUpload: (uploadId) => {
    const entry = get().uploads[uploadId];
    if (!entry || entry.status !== "error") return null;

    const newAbortController = new AbortController();
    set((state) => {
      const entry = state.uploads[uploadId];
      if (!entry) return state;
      return {
        uploads: {
          ...state.uploads,
          [uploadId]: {
            ...entry,
            status: "uploading",
            progress: 0,
            error: undefined,
            abortController: newAbortController,
          },
        },
      };
    });
    return newAbortController;
  },

  cleanup: () => {
    const { uploads } = get();
    for (const entry of Object.values(uploads)) {
      entry.abortController.abort();
      URL.revokeObjectURL(entry.blobUrl);
    }
    set({ uploads: {} });
  },

  getUpload: (uploadId) => {
    return get().uploads[uploadId];
  },
}));
