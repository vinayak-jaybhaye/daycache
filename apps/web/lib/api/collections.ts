import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface CollectionCreateRequest {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface CollectionUpdateRequest {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface CollectionResponse {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  color?: string;
  icon?: string;
  entry_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionEntryRequest {
  entry_id: string;
}

// ============ Collections API ============

export const collectionsApi = {
  /**
   * List all collections for the authenticated user
   */
  list: async (): Promise<CollectionResponse[]> => {
    const response = await api.get("/api/v1/collections");
    return response.data;
  },

  /**
   * Create a new collection
   */
  create: async (data: CollectionCreateRequest): Promise<CollectionResponse> => {
    const response = await api.post("/api/v1/collections", data);
    return response.data;
  },

  /**
   * Get a specific collection by ID
   */
  get: async (id: string): Promise<CollectionResponse> => {
    const response = await api.get(`/api/v1/collections/${id}`);
    return response.data;
  },

  /**
   * Update a collection
   */
  update: async (id: string, data: CollectionUpdateRequest): Promise<CollectionResponse> => {
    const response = await api.patch(`/api/v1/collections/${id}`, data);
    return response.data;
  },

  /**
   * Delete a collection
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/collections/${id}`);
  },

  /**
   * Add an entry to a collection
   */
  addEntry: async (id: string, entryId: string): Promise<void> => {
    await api.post(`/api/v1/collections/${id}/entries`, { journal_entry_id: entryId });
  },

  /**
   * Remove an entry from a collection
   */
  removeEntry: async (id: string, entryId: string): Promise<void> => {
    await api.delete(`/api/v1/collections/${id}/entries/${entryId}`);
  },
};
