import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface SummaryResponse {
  id: string;
  content: string;
  summary_type: string;
  key_themes?: string[];
  sentiment?: string;
  created_at: string;
}

export interface DaySummaryParams {
  date: string;
}

export interface WeeklySummaryParams {
  targetDate: string;
}

export interface MonthlySummaryParams {
  year: number;
  month: number;
}

export interface YearlySummaryParams {
  year: number;
}

// ============ AI Summaries API ============

export const aiApi = {
  /**
   * Generate a summary for a specific entry
   */
  generateEntrySummary: async (entryId: string): Promise<SummaryResponse> => {
    const response = await api.get(`/api/v1/ai/summaries/entry/${entryId}`);
    return response.data;
  },

  /**
   * Generate a summary for a specific day
   */
  generateDaySummary: async (dateVal: string): Promise<SummaryResponse> => {
    const response = await api.get(`/api/v1/ai/summaries/day/${dateVal}`);
    return response.data;
  },

  /**
   * Generate a summary for a specific week
   */
  generateWeeklySummary: async (targetDate: string): Promise<SummaryResponse> => {
    const response = await api.get(`/api/v1/ai/summaries/week/${targetDate}`);
    return response.data;
  },

  /**
   * Generate a summary for a specific month
   */
  generateMonthlySummary: async (year: number, month: number): Promise<SummaryResponse> => {
    const response = await api.get(`/api/v1/ai/summaries/month/${year}/${month}`);
    return response.data;
  },

  /**
   * Generate a summary for a specific year
   */
  generateYearlySummary: async (year: number): Promise<SummaryResponse> => {
    const response = await api.get(`/api/v1/ai/summaries/year/${year}`);
    return response.data;
  },
};

// ============ Recall API ============

export interface RecallSession {
  id: string;
  user_id: string;
  created_at: string;
}

export interface RecallMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  isGreeting?: boolean; // Is this a greeting message
  sources?: Array<{ id: string; date: string; title: string; snippet: string }>; // Source entries
  retrieved_entries?: Array<{
    entry_id: string;
    day_date: string;
    entry_title: string;
    snippet?: string;
  }>; // Raw retrieved entries from the API
  created_at: string;
}

export interface RecallMessageRequest {
  content: string;
}

export const recallApi = {
  /**
   * Start a new recall session or get the current one
   */
  session: async (): Promise<RecallSession> => {
    const response = await api.get("/api/v1/recall/session");
    return response.data;
  },

  /**
   * Send a message and get a response in a recall session
   */
  sendMessage: async (data: RecallMessageRequest): Promise<Response> => {
    return fetch(`${API_BASE_URL}/api/v1/recall/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      credentials: "include",
    });
  },

  /**
   * List all messages in the current recall session
   */
  listMessages: async (skip?: number, limit?: number): Promise<RecallMessage[]> => {
    const response = await api.get("/api/v1/recall/messages", {
      params: { skip, limit },
    });
    return response.data;
  },

  /**
   * Get a specific message
   */
  getMessage: async (messageId: string): Promise<RecallMessage> => {
    const response = await api.get(`/api/v1/recall/messages/${messageId}`);
    return response.data;
  },

  /**
   * Delete a specific message
   */
  deleteMessage: async (messageId: string): Promise<void> => {
    await api.delete(`/api/v1/recall/messages/${messageId}`);
  },

  /**
   * Delete all messages for a given date
   */
  deleteMessagesByDate: async (dateVal: string): Promise<void> => {
    await api.delete(`/api/v1/recall/messages?date=${dateVal}`);
  },
};

// ============ Reflect API ============

export interface ReflectMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  date: string;
  created_at: string;
}

export interface ReflectMessageRequest {
  content: string;
}

export const reflectApi = {
  /**
   * Send a message and get reflection guidance
   */
  sendMessage: async (data: ReflectMessageRequest): Promise<Response> => {
    return fetch(`${API_BASE_URL}/api/v1/reflect/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      credentials: "include",
    });
  },

  /**
   * List all reflection messages for today
   */
  listTodayMessages: async (): Promise<ReflectMessage[]> => {
    const response = await api.get("/api/v1/reflect/today");
    return response.data;
  },
};

// Merge all AI APIs into single aiApi object
export const aiApi_full = {
  ...aiApi,
  ...recallApi,
  ...reflectApi,
  // Aliases for backward compatibility
  getRecallMessages: () => recallApi.listMessages(),
  sendRecallMessage: (content: string) => recallApi.sendMessage({ content }),
  getReflectMessages: () => reflectApi.listTodayMessages(),
  sendReflectMessage: (content: string) => reflectApi.sendMessage({ content }),
};

// Re-export as aiApi for backward compatibility
Object.assign(aiApi, aiApi_full);
