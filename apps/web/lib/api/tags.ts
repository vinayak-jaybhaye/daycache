import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface TagResponse {
  id: string;
  name: string;
  color: string;
  entry_count: number;
  created_at: string;
}

export interface TagCreate {
  name: string;
  color?: string;
}

export interface TagUpdate {
  name?: string;
  color?: string;
}

// ============ Tags API ============

export const tagsApi = {
  /**
   * Retrieve all tags belonging to the authenticated user
   */
  list: async (): Promise<TagResponse[]> => {
    const response = await api.get("/api/v1/tags");
    return response.data;
  },

  /**
   * Create a new tag for the authenticated user
   */
  create: async (data: TagCreate): Promise<TagResponse> => {
    const response = await api.post("/api/v1/tags", data);
    return response.data;
  },

  /**
   * Retrieve details of a specific tag by ID
   */
  get: async (id: string): Promise<TagResponse> => {
    const response = await api.get(`/api/v1/tags/${id}`);
    return response.data;
  },

  /**
   * Update metadata of an existing tag
   */
  update: async (id: string, data: TagUpdate): Promise<TagResponse> => {
    const response = await api.patch(`/api/v1/tags/${id}`, data);
    return response.data;
  },

  /**
   * Delete a tag
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/tags/${id}`);
  },
};
