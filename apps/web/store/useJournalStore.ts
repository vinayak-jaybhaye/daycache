import { create } from "zustand";
import {
  entriesApi,
  type JournalEntryResponse,
  type DayResponse,
  type MoodResponse,
  type MediaUploadResponse,
} from "@/lib/api/entries";
import { isAxiosError } from "axios";

export interface JournalFilter {
  type: "all" | "collection" | "tag" | "favorite" | "date";
  id?: string;
  date?: string;
}

interface JournalState {
  entries: Record<string, JournalEntryResponse>;
  timeline: string[]; // array of IDs
  days: Record<string, DayResponse>; // key: date string YYYY-MM-DD
  availableMoods: MoodResponse[];
  activeEntryId: string | null;
  nextCursor: string | null;
  isLoading: boolean;
  currentFilter: JournalFilter;

  setActiveEntry: (id: string | null) => void;
  setFilter: (filter: JournalFilter) => void;
  fetchEntries: (reset?: boolean) => Promise<void>;
  fetchEntry: (id: string) => Promise<void>;
  fetchDays: (startDate: string, endDate: string) => Promise<void>;
  createEntry: (data: Partial<JournalEntryResponse>) => Promise<JournalEntryResponse>;
  updateEntry: (
    id: string,
    data: Partial<JournalEntryResponse> & { media_ids?: string[] },
  ) => Promise<void>;
  deleteEntry: (id: string) => Promise<void>;

  fetchMoods: () => Promise<void>;
  addMood: (entryId: string, moodId: string, intensity: number) => Promise<void>;
  removeMood: (entryId: string, moodId: string) => Promise<void>;

  addTag: (entryId: string, tagId: string) => Promise<void>;
  removeTag: (entryId: string, tagId: string) => Promise<void>;

  requestMediaUpload: (
    entryId: string,
    mediaType: "image" | "video",
    mimeType: string,
    filename: string,
    size: number,
  ) => Promise<MediaUploadResponse>;
  confirmMediaUpload: (entryId: string, mediaId: string) => Promise<void>;
  removeMedia: (entryId: string, mediaId: string) => Promise<void>;
  ensureEntry: () => Promise<string>;
}

export const useJournalStore = create<JournalState>((set, get) => ({
  entries: {},
  timeline: [],
  days: {},
  availableMoods: [],
  activeEntryId: null,
  nextCursor: null,
  isLoading: false,
  currentFilter: { type: "all" },

  setActiveEntry: (id) => set({ activeEntryId: id }),

  setFilter: (filter) => {
    set({ currentFilter: filter });
    get().fetchEntries(true);
  },

  fetchEntry: async (id: string) => {
    try {
      const entry = await entriesApi.get(id);
      set((state) => ({
        entries: { ...state.entries, [id]: entry },
      }));
    } catch (error) {
      console.error("Failed to fetch entry", error);
    }
  },

  fetchDays: async (startDate: string, endDate: string) => {
    try {
      const days = await entriesApi.listDays(startDate, endDate);
      const newDays = { ...get().days };
      days.forEach((day) => {
        newDays[day.date] = day;
      });
      set({ days: newDays });
    } catch (error) {
      console.error("Failed to fetch days", error);
    }
  },

  fetchEntries: async (reset = false) => {
    const { nextCursor, isLoading, entries, timeline, currentFilter } = get();

    if (isLoading || (!reset && nextCursor === null && timeline.length > 0)) return;

    set({ isLoading: true });
    try {
      const apiFilters: Record<string, unknown> = {};
      if (currentFilter.type !== "all") {
        if (currentFilter.type === "collection") apiFilters.collection_id = currentFilter.id;
        if (currentFilter.type === "tag") apiFilters.tag_id = currentFilter.id;
        if (currentFilter.type === "favorite") apiFilters.is_favorite = true;
        if (currentFilter.type === "date") apiFilters.date = currentFilter.date;
      }

      if (!reset && nextCursor) {
        apiFilters.cursor = nextCursor;
      } else if (!reset) {
        // Do not fetch if no nextCursor and not resetting
        set({ isLoading: false });
        return;
      }

      const data = await entriesApi.list(
        Object.keys(apiFilters).length > 0 ? apiFilters : undefined,
      );

      const newEntries = { ...(reset ? {} : entries) };
      const newTimeline = reset ? [] : [...timeline];

      data.items.forEach((entry) => {
        newEntries[entry.id] = entry;
        if (!newTimeline.includes(entry.id)) {
          newTimeline.push(entry.id);
        }
      });

      set({
        entries: newEntries,
        timeline: newTimeline,
        nextCursor: data.next_cursor || null,
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false });
      console.error("Failed to fetch entries", error);
    }
  },

  createEntry: async (data) => {
    try {
      const payload = {
        title: data.title ?? undefined,
        content:
          typeof data.content === "string" ? JSON.parse(data.content || "{}") : data.content || {},
        date: data.date || new Date().toISOString().split("T")[0],
      };
      const entry = await entriesApi.create(payload);

      set((state) => ({
        entries: { ...state.entries, [entry.id]: entry },
        timeline: [entry.id, ...state.timeline],
        activeEntryId: entry.id,
      }));
      return entry;
    } catch (error) {
      console.error("Failed to create entry", error);
      throw error;
    }
  },

  updateEntry: async (id, data) => {
    try {
      const entry = get().entries[id];
      const rawContent = data.content || entry?.content || "{}";
      const parsedContent = typeof rawContent === "string" ? JSON.parse(rawContent) : rawContent;
      const payload = {
        title: data.title ?? undefined,
        content: parsedContent,
        is_favorite: data.is_favorite,
        media_ids: data.media_ids,
        version: entry?.version || 0,
      };

      // Forward media_ids for backend reconciliation if provided
      if ("media_ids" in data && data.media_ids !== undefined) {
        payload.media_ids = data.media_ids;
      }

      try {
        const updated = await entriesApi.update(id, payload);
        set((state) => ({
          entries: { ...state.entries, [id]: updated },
        }));
      } catch (err: unknown) {
        if (isAxiosError(err) && err.response?.status === 409) {
          // Version conflict, fetch latest and apply our local edits on top of it.
          // For now, let's just fetch the latest entry and override to avoid data corruption
          console.warn("Version conflict (409), refreshing entry from server");
          const latest = await entriesApi.get(id);
          set((state) => ({
            entries: { ...state.entries, [id]: latest },
          }));

          // Re-try the patch with the new version
          const retryPayload = {
            ...payload,
            version: latest.version,
          };
          const updatedAgain = await entriesApi.update(id, retryPayload);
          set((state) => ({
            entries: { ...state.entries, [id]: updatedAgain },
          }));
        } else {
          throw err;
        }
      }
    } catch (error) {
      console.error("Failed to update entry", error);
      throw error;
    }
  },

  deleteEntry: async (id) => {
    try {
      await entriesApi.delete(id);
      set((state) => {
        const newEntries = { ...state.entries };
        delete newEntries[id];
        return {
          entries: newEntries,
          timeline: state.timeline.filter((entryId) => entryId !== id),
          activeEntryId: state.activeEntryId === id ? null : state.activeEntryId,
        };
      });
    } catch (error) {
      console.error("Failed to delete entry", error);
      throw error;
    }
  },

  fetchMoods: async () => {
    try {
      const moods = await entriesApi.listMoods();
      set({ availableMoods: moods || [] });
    } catch (error) {
      console.error("Failed to fetch moods", error);
    }
  },

  addMood: async (entryId, moodId) => {
    // Note: intensity is not sent to the backend, it's for display only
    await entriesApi.addMood(entryId, moodId);
    const updated = await entriesApi.get(entryId);
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  removeMood: async (entryId, moodId) => {
    await entriesApi.removeMood(entryId, moodId);
    const updated = await entriesApi.get(entryId);
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  addTag: async (entryId, tagId) => {
    await entriesApi.addTag(entryId, tagId);
    const updated = await entriesApi.get(entryId);
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  removeTag: async (entryId, tagId) => {
    await entriesApi.removeTag(entryId, tagId);
    const updated = await entriesApi.get(entryId);
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  requestMediaUpload: async (entryId, mediaType, mimeType, filename, size) => {
    return await entriesApi.requestMediaUpload(entryId, mediaType, mimeType, filename, size);
  },

  confirmMediaUpload: async (entryId, mediaId) => {
    const updated = await entriesApi.confirmMediaUpload(entryId, mediaId);
    // confirmMediaUpload returns the updated entry, force type cast
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  removeMedia: async (entryId, mediaId) => {
    await entriesApi.deleteMedia(entryId, mediaId);
    const updated = await entriesApi.get(entryId);
    set((state) => ({ entries: { ...state.entries, [entryId]: updated } }));
  },

  ensureEntry: async () => {
    const { activeEntryId, createEntry } = get();
    if (activeEntryId && activeEntryId !== "new") return activeEntryId;
    const entry = await createEntry({
      title: "",
      content: {},
      date: new Date().toISOString().split("T")[0],
    });
    return entry.id;
  },
}));
