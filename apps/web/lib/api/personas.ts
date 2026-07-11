import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface PersonaListItem {
  id: string;
  name: string;
  description?: string;
  emoji?: string;
  system_prompt?: string;
}

export interface PersonaResponse {
  id: string;
  name: string;
  description?: string;
  emoji?: string;
  system_prompt?: string;
  created_at: string;
  updated_at: string;
}

export interface PersonaCreateRequest {
  name: string;
  description?: string;
  emoji?: string;
  system_prompt?: string;
}

export interface PersonaUpdateRequest {
  name?: string;
  description?: string;
  emoji?: string;
  system_prompt?: string;
}

// ============ Personas API ============

export const personasApi = {
  /**
   * List all available personas (system defaults + user custom personas)
   */
  list: async (): Promise<PersonaListItem[]> => {
    const response = await api.get("/api/v1/personas");
    return response.data;
  },

  /**
   * Get a specific persona
   */
  get: async (id: string): Promise<PersonaResponse> => {
    const response = await api.get(`/api/v1/personas/${id}`);
    return response.data;
  },

  /**
   * Create a custom persona
   */
  create: async (data: PersonaCreateRequest): Promise<PersonaResponse> => {
    const response = await api.post("/api/v1/personas", data);
    return response.data;
  },

  /**
   * Update a persona
   */
  update: async (id: string, data: PersonaUpdateRequest): Promise<PersonaResponse> => {
    const response = await api.patch(`/api/v1/personas/${id}`, data);
    return response.data;
  },

  /**
   * Delete a persona
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/personas/${id}`);
  },
};
