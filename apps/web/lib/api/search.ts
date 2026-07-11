import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface SearchResult {
  id: string;
  title?: string;
  content: string;
  entry_id: string;
  entry?: { id: string; title?: string; content: string; content_text?: string; date?: string }; // Entry details
  day_date?: string; // Day date
  highlight_snippet?: string; // Highlighted snippet
  created_at: string;
  score?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface SearchParams {
  q: string;
  skip?: number;
  limit?: number;
}

// ============ Search API ============

export const searchApi = {
  /**
   * Search entries by content and metadata
   */
  search: async (params: SearchParams): Promise<SearchResult[]> => {
    const response = await api.get("/api/v1/search", { params });
    return response.data;
  },
};
