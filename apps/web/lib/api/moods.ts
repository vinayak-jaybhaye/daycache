import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface MoodResponse {
  id: string;
  user_id: string;
  name: string;
  emoji?: string;
  color?: string;
  intensity?: number;
  created_at: string;
  updated_at: string;
}

export interface MoodCreate {
  name: string;
  emoji?: string;
  color?: string;
  intensity?: number;
}

export interface MoodUpdate {
  name?: string;
  emoji?: string;
  color?: string;
  intensity?: number;
}

// ============ Moods API ============

export const moodsApi = {
  /**
   * List all moods (likely system defaults + user custom moods)
   */
  list: async (): Promise<MoodResponse[]> => {
    const response = await api.get("/api/v1/moods");
    return response.data;
  },

  /**
   * Create a custom mood
   */
  create: async (data: MoodCreate): Promise<MoodResponse> => {
    const response = await api.post("/api/v1/moods", data);
    return response.data;
  },

  /**
   * Update a mood
   */
  update: async (id: string, data: MoodUpdate): Promise<MoodResponse> => {
    const response = await api.patch(`/api/v1/moods/${id}`, data);
    return response.data;
  },

  /**
   * Delete a mood
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/moods/${id}`);
  },
};
