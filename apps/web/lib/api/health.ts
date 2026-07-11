import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface HealthResponse {
  status: string;
  [key: string]: string;
}

// ============ Health API ============

export const healthApi = {
  /**
   * Liveness check - Returns immediately
   * Used by load balancers to verify the process is alive
   */
  health: async (): Promise<HealthResponse> => {
    const response = await api.get("/api/v1/health");
    return response.data;
  },

  /**
   * Readiness check - Verifies infrastructure dependencies
   * Returns 200 only when all critical services are reachable
   */
  ready: async (): Promise<void> => {
    await api.get("/api/v1/ready");
  },
};
