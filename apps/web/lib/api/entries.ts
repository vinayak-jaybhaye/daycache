import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface EntryCreateRequest {
  date: string;
  title?: string;
  content?: Record<string, unknown>;
  is_favorite?: boolean;
  tag_ids?: string[];
  media_ids?: string[];
}

export interface EntryUpdateRequest {
  title?: string;
  content?: Record<string, unknown>;
  is_favorite?: boolean;
  media_ids?: string[];
  version: number;
}

export interface MoodResponse {
  id: string;
  user_id: string;
  name: string;
  emoji?: string;
  color?: string;
  intensity?: number;
  created_at: string;
}

export interface TagResponse {
  id: string;
  user_id: string;
  name: string;
  color?: string;
  created_at: string;
  updated_at: string;
}

export interface MediaResponse {
  id: string;
  entry_id: string;
  media_type: string;
  url: string;
  read_url?: string; // Read URL (alias for url)
  upload_status?: string;
  processing_status?: string;
  thumbnail_url?: string;
  blurhash?: string;
  width?: number;
  height?: number;
  alt_text?: string;
  size: number;
  created_at: string;
}

export interface EntryResponse {
  id: string;
  day_id: string;
  date: string;
  title: string | null;
  content: Record<string, unknown>; // ProseMirror JSON
  content_text: string | null;
  word_count: number;
  is_favorite: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  tags?: TagResponse[];
  moods?: MoodResponse[];
  media?: MediaResponse[];
}

export interface MediaUploadResponse {
  media_id: string;
  upload_url: string;
  upload_expires_at: string;
}

export interface ListEntriesParams {
  limit?: number;
  cursor?: string;
  collection_id?: string;
  tag_id?: string;
  date?: string;
  is_favorite?: boolean;
}

export interface EntryListResponse {
  items: EntryResponse[];
  total: number;
  next_cursor?: string | null;
}

// Type aliases for backward compatibility with existing code
export type JournalEntryResponse = EntryResponse;
export type DayResponse = {
  date: string;
  entries: EntryResponse[];
  location?: { name: string };
  weather?: { condition: string };
};
export type PaginatedJournalEntriesResponse = EntryListResponse;
export type EntryMoodResponse = MoodResponse;
export type MediaStatusResponse = MediaResponse;
export type TagInfo = TagResponse;

// ============ Entries API ============

export const entriesApi = {
  /**
   * Create a new journal entry
   */
  create: async (data: EntryCreateRequest): Promise<EntryResponse> => {
    const response = await api.post("/api/v1/entries", data);
    return response.data;
  },

  /**
   * List all entries for the authenticated user
   */
  list: async (params?: ListEntriesParams): Promise<EntryListResponse> => {
    const response = await api.get("/api/v1/entries", { params });
    return response.data;
  },

  /**
   * Get a specific entry by ID
   */
  get: async (id: string): Promise<EntryResponse> => {
    const response = await api.get(`/api/v1/entries/${id}`);
    return response.data;
  },

  /**
   * Update an entry
   */
  update: async (id: string, data: EntryUpdateRequest): Promise<EntryResponse> => {
    const response = await api.patch(`/api/v1/entries/${id}`, data);
    return response.data;
  },

  /**
   * Delete an entry
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/entries/${id}`);
  },

  /**
   * Add a tag to an entry
   */
  addTag: async (entryId: string, tagId: string): Promise<void> => {
    await api.post(`/api/v1/entries/${entryId}/tags`, { tag_id: tagId });
  },

  /**
   * Remove a tag from an entry
   */
  removeTag: async (entryId: string, tagId: string): Promise<void> => {
    await api.delete(`/api/v1/entries/${entryId}/tags/${tagId}`);
  },

  /**
   * Add a mood to an entry
   */
  addMood: async (entryId: string, moodId: string): Promise<void> => {
    await api.post(`/api/v1/entries/${entryId}/moods`, { mood_id: moodId });
  },

  /**
   * Remove a mood from an entry
   */
  removeMood: async (entryId: string, moodId: string): Promise<void> => {
    await api.delete(`/api/v1/entries/${entryId}/moods/${moodId}`);
  },

  /**
   * Request a presigned PUT URL to upload media to an entry
   */
  requestMediaUpload: async (
    entryId: string,
    mediaType: string,
    mimeType: string,
    filename: string,
    size: number,
  ): Promise<MediaUploadResponse> => {
    const response = await api.post(`/api/v1/entries/${entryId}/media/upload`, {
      media_type: mediaType,
      mime_type: mimeType,
      filename,
      size,
    });
    return response.data;
  },

  /**
   * Confirm media upload and enqueue background processing, returns the updated entry
   */
  confirmMediaUpload: async (entryId: string, mediaId: string): Promise<EntryResponse> => {
    const response = await api.post(`/api/v1/entries/${entryId}/media/${mediaId}/confirm`);
    return response.data;
  },

  /**
   * Delete media from an entry
   */
  deleteMedia: async (entryId: string, mediaId: string): Promise<void> => {
    await api.delete(`/api/v1/entries/${entryId}/media/${mediaId}`);
  },

  /**
   * List days with entries
   */
  listDays: async (startDate: string, endDate: string): Promise<DayResponse[]> => {
    const response = await api.get("/api/v1/days", {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  },

  /**
   * List all available moods
   */
  listMoods: async (): Promise<MoodResponse[]> => {
    const response = await api.get("/api/v1/moods");
    return response.data;
  },
};
