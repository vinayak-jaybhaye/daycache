import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface UserRegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface UserLoginRequest {
  email: string;
  password: string;
  installation_id: string;
  device_name?: string;
  platform: "web" | "ios" | "android" | "macos" | "windows" | "linux";
}

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  is_verified: boolean;
  created_at: string;
}

export interface SessionResponse {
  id: string;
  user_id: string;
  device_id: string;
  ip_address: string;
  user_agent: string;
  last_activity_at: string;
  expires_at: string;
  created_at: string;
}

export interface DeviceResponse {
  id: string;
  user_id: string;
  device_name: string;
  device_type: string;
  os: string;
  last_ip: string;
  sessions: SessionResponse[];
  created_at: string;
  last_activity_at: string;
}

// ============ Auth API ============

export const authApi = {
  /**
   * Register a new email/password account
   */
  register: async (data: UserRegisterRequest): Promise<UserResponse> => {
    const response = await api.post("/api/v1/auth/register", data);
    return response.data;
  },

  /**
   * Authenticate credentials and establish a secure HTTP-Only cookie session
   */
  login: async (data: UserLoginRequest): Promise<UserResponse> => {
    const response = await api.post("/api/v1/auth/login", data);
    return response.data;
  },

  /**
   * Revoke the current active session and clear the session cookie
   */
  logout: async (): Promise<void> => {
    await api.post("/api/v1/auth/logout");
  },

  /**
   * Return the authenticated user's profile metadata
   */
  getMe: async (): Promise<UserResponse> => {
    const response = await api.get("/api/v1/auth/me");
    return response.data;
  },

  /**
   * List all active unexpired sessions for the authenticated user
   */
  listSessions: async (): Promise<SessionResponse[]> => {
    const response = await api.get("/api/v1/auth/sessions");
    return response.data;
  },

  /**
   * Revoke all active sessions for the user except the current one
   */
  revokeOtherSessions: async (): Promise<void> => {
    await api.delete("/api/v1/auth/sessions");
  },

  /**
   * List all user devices with their active sessions grouped under them
   */
  listDevices: async (): Promise<DeviceResponse[]> => {
    const response = await api.get("/api/v1/auth/devices");
    return response.data;
  },

  /**
   * Revoke a specific session
   */
  revokeSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/api/v1/auth/sessions/${sessionId}`);
  },
};
