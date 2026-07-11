import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface DayEntryResponse {
  id: string;
  title?: string;
  content: string;
  created_at: string;
}

export interface DayResponse {
  date: string;
  entry_count: number;
  mood_count: number;
  entries: DayEntryResponse[];
  summary?: string;
  created_at: string;
  updated_at: string;
}

export interface DayListResponse {
  items: DayResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface ListDaysParams {
  skip?: number;
  limit?: number;
  from_date?: string;
  to_date?: string;
}

// ============ Days API ============

export const daysApi = {
  /**
   * List days with entries for the authenticated user
   */
  list: async (params?: ListDaysParams): Promise<DayListResponse> => {
    const response = await api.get("/api/v1/days", { params });
    return response.data;
  },

  /**
   * Get a specific day's entries and metadata
   */
  get: async (date: string): Promise<DayResponse> => {
    const response = await api.get(`/api/v1/days/${date}`);
    return response.data;
  },
};
