import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

// ============ Types ============

export interface UserProfileResponse {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  display_name?: string;
  bio?: string;
  avatar_url?: string;
  timezone: string;
  email_verified_at?: string;
  created_at: string;
  updated_at: string;
}

export interface UpdateProfileRequest {
  first_name?: string;
  last_name?: string;
  display_name?: string;
  bio?: string;
  timezone?: string;
}

export type Theme = "light" | "dark" | "system" | "morning" | "midnight" | "forest" | "cinematic";

export interface SettingsResponse {
  id: string;
  user_id: string;
  theme: Theme;
  language: string;
  locale?: string; // Locale setting
  timezone?: string; // Timezone setting
  notifications_enabled: boolean;
  email_digest_frequency?: string;
  ai_features_enabled: boolean;
  ai_persona_name?: string; // AI persona name
  editor_font?: "Inter" | "Caveat" | "Serif"; // Editor font choice
  data_retention_days?: number;
  created_at: string;
  updated_at: string;
}

export interface UpdateSettingsRequest {
  theme?: Theme;
  language?: string;
  notifications_enabled?: boolean;
  email_digest_frequency?: string;
  ai_features_enabled?: boolean;
  data_retention_days?: number;
}

export interface MediaUploadResponse {
  id: string;
  upload_url: string;
  media_type: string;
  size?: number;
  created_at: string;
}

export interface AvatarUploadRequest {
  media_type: string;
  size: number;
}

export interface PersonaListItem {
  name: string;
  tagline: string;
}

export interface PersonasListResponse {
  personas: PersonaListItem[];
  default: string;
}

// ============ Users API ============

export const usersApi = {
  /**
   * Return the authenticated user's profile
   */
  getProfile: async (): Promise<UserProfileResponse> => {
    const response = await api.get("/api/v1/users/me");
    return response.data;
  },

  /**
   * Partially update the authenticated user's mutable profile fields
   */
  updateProfile: async (data: UpdateProfileRequest): Promise<UserProfileResponse> => {
    const response = await api.patch("/api/v1/users/me", data);
    return response.data;
  },

  /**
   * Soft-delete the authenticated user account and revoke all sessions
   */
  deleteAccount: async (): Promise<void> => {
    await api.delete("/api/v1/users/me");
  },

  /**
   * Request a presigned PUT URL to upload a new avatar image
   */
  requestAvatarUpload: async (mimeType: string, size: number): Promise<MediaUploadResponse> => {
    const response = await api.post("/api/v1/users/me/avatar", {
      mime_type: mimeType,
      size,
    });
    return response.data;
  },

  /**
   * Confirm the avatar upload and enqueue background processing
   */
  confirmAvatarUpload: async (): Promise<UserProfileResponse> => {
    const response = await api.post("/api/v1/users/me/avatar/confirm");
    return response.data;
  },

  /**
   * Remove the user's avatar
   */
  removeAvatar: async (): Promise<UserProfileResponse> => {
    const response = await api.delete("/api/v1/users/me/avatar");
    return response.data;
  },

  /**
   * Return the authenticated user's application settings
   */
  getSettings: async (): Promise<SettingsResponse> => {
    const response = await api.get("/api/v1/users/me/settings");
    return response.data;
  },

  /**
   * Partially update the authenticated user's application settings
   */
  updateSettings: async (data: UpdateSettingsRequest): Promise<SettingsResponse> => {
    const response = await api.patch("/api/v1/users/me/settings", data);
    return response.data;
  },

  /**
   * Get available AI personas
   */
  getPersonas: async (): Promise<PersonasListResponse> => {
    const response = await api.get("/api/v1/personas");
    return response.data;
  },

  /**
   * Upload avatar file
   */
  uploadAvatar: async (file: File): Promise<MediaUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await api.post("/api/v1/users/me/avatar/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },
};

// ============ Settings API (alternative endpoints) ============

export const settingsApi = {
  /**
   * Return the authenticated user's application settings
   */
  getSettings: async (): Promise<SettingsResponse> => {
    const response = await api.get("/api/v1/settings");
    return response.data;
  },

  /**
   * Partially update the authenticated user's application settings
   */
  updateSettings: async (data: UpdateSettingsRequest): Promise<SettingsResponse> => {
    const response = await api.patch("/api/v1/settings", data);
    return response.data;
  },
};
