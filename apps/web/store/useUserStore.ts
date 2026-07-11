import { create } from "zustand";
import { authApi, SessionResponse, DeviceResponse } from "@/lib/api/auth";
import { usersApi, UserProfileResponse, SettingsResponse, PersonaListItem } from "@/lib/api/users";

interface UserState {
  profile: UserProfileResponse | null;
  settings: SettingsResponse | null;
  availablePersonas: PersonaListItem[];
  isAuthenticated: boolean;
  isLoading: boolean;
  sessions: SessionResponse[];
  devices: DeviceResponse[];

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, display_name: string) => Promise<void>;
  logout: () => Promise<void>;

  fetchMe: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  fetchSessions: () => Promise<void>;
  fetchDevices: () => Promise<void>;
  revokeSession: (sessionId: string) => Promise<void>;
  revokeOtherSessions: () => Promise<void>;
  updateProfile: (updates: Partial<UserProfileResponse>) => Promise<void>;
  updateSettings: (updates: Partial<SettingsResponse>) => Promise<void>;
  fetchPersonas: () => Promise<void>;

  // Avatar
  uploadAvatar: (file: File) => Promise<void>;
  removeAvatar: () => Promise<void>;
}

export const useUserStore = create<UserState>((set, get) => ({
  profile: null,
  settings: null,
  availablePersonas: [],
  isAuthenticated: false,
  isLoading: true, // initial load state
  sessions: [],
  devices: [],

  login: async (email, password) => {
    let installationId = "";
    if (typeof window !== "undefined") {
      installationId = localStorage.getItem("daycache_installation_id") || "";
      if (!installationId) {
        installationId = crypto.randomUUID();
        localStorage.setItem("daycache_installation_id", installationId);
      }
    }

    await authApi.login({
      email,
      password,
      installation_id: installationId,
      device_name: navigator.userAgent.substring(0, 100),
      platform: "web",
    });
    await get().fetchMe();
  },

  register: async (email, password, display_name) => {
    await authApi.register({ email, password, display_name });
  },

  logout: async () => {
    try {
      await authApi.logout();
    } finally {
      set({ profile: null, settings: null, isAuthenticated: false });
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  },

  fetchMe: async () => {
    try {
      const [profile, settings] = await Promise.all([
        usersApi.getProfile(),
        usersApi.getSettings(),
      ]);
      set({
        profile,
        settings,
        isAuthenticated: true,
        isLoading: false,
      });
      // Optionally fetch sessions and devices in the background
      get().fetchSessions();
      get().fetchDevices();
    } catch {
      set({
        profile: null,
        settings: null,
        isAuthenticated: false,
        isLoading: false,
        sessions: [],
      });
    }
  },

  deleteAccount: async () => {
    await usersApi.deleteAccount();
    set({ profile: null, settings: null, isAuthenticated: false, sessions: [] });
  },

  fetchSessions: async () => {
    try {
      const sessions = await authApi.listSessions();
      set({ sessions });
    } catch (err) {
      console.error("Failed to fetch sessions", err);
    }
  },

  fetchDevices: async () => {
    try {
      const devices = await authApi.listDevices();
      set({ devices });
    } catch (err) {
      console.error("Failed to fetch devices", err);
    }
  },

  revokeSession: async (sessionId: string) => {
    await authApi.revokeSession(sessionId);
    await get().fetchSessions();
    await get().fetchDevices();
  },

  revokeOtherSessions: async () => {
    await authApi.revokeOtherSessions();
    await get().fetchSessions(); // refresh to get just the current one
    await get().fetchDevices();
  },

  updateProfile: async (updates) => {
    // Optimistic update
    const previousProfile = get().profile;
    set((state) => ({
      profile: state.profile ? { ...state.profile, ...updates } : null,
    }));

    try {
      const profile = await usersApi.updateProfile(updates);
      set({ profile });
    } catch (error) {
      // Revert on error
      set({ profile: previousProfile });
      throw error;
    }
  },

  updateSettings: async (updates) => {
    // Optimistic update
    const previousSettings = get().settings;
    set((state) => ({
      settings: state.settings ? { ...state.settings, ...updates } : null,
    }));

    try {
      const settings = await usersApi.updateSettings(updates);
      set({ settings });
    } catch (error) {
      set({ settings: previousSettings });
      throw error;
    }
  },

  fetchPersonas: async () => {
    try {
      const response = await usersApi.getPersonas();
      set({ availablePersonas: response.personas || [] });
    } catch (err) {
      console.error("Failed to fetch personas", err);
    }
  },

  uploadAvatar: async (file: File) => {
    try {
      // 1. Request upload URL
      const uploadResponse = await usersApi.requestAvatarUpload(file.type, file.size);

      // 2. Upload to S3 directly using standard fetch (not axios which might have auth headers breaking S3)
      const uploadRes = await fetch(uploadResponse.upload_url, {
        method: "PUT",
        headers: {
          "Content-Type": file.type,
        },
        body: file,
      });

      if (!uploadRes.ok) {
        throw new Error("Failed to upload file to storage");
      }

      // 3. Confirm upload
      const profile = await usersApi.confirmAvatarUpload();
      set({ profile });
    } catch (err) {
      console.error("Failed to upload avatar", err);
      throw err;
    }
  },

  removeAvatar: async () => {
    try {
      const profile = await usersApi.removeAvatar();
      set({ profile });
    } catch (err) {
      console.error("Failed to remove avatar", err);
      throw err;
    }
  },
}));
