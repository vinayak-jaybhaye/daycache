import { create } from "zustand";
import { tagsApi, TagResponse, TagCreate, TagUpdate } from "@/lib/api/tags";

interface TagState {
  tags: TagResponse[];
  isLoading: boolean;

  fetchTags: () => Promise<void>;
  createTag: (data: TagCreate) => Promise<TagResponse>;
  updateTag: (id: string, data: TagUpdate) => Promise<TagResponse>;
  deleteTag: (id: string) => Promise<void>;
}

export const useTagStore = create<TagState>((set) => ({
  tags: [],
  isLoading: false,

  fetchTags: async () => {
    set({ isLoading: true });
    try {
      const tags = await tagsApi.list();
      set({ tags, isLoading: false });
    } catch (error) {
      console.error("Failed to fetch tags", error);
      set({ isLoading: false });
    }
  },

  createTag: async (data) => {
    const newTag = await tagsApi.create(data);
    set((state) => ({
      tags: [...state.tags, newTag],
    }));
    return newTag;
  },

  updateTag: async (id, data) => {
    const updatedTag = await tagsApi.update(id, data);
    set((state) => ({
      tags: state.tags.map((t) => (t.id === id ? updatedTag : t)),
    }));
    return updatedTag;
  },

  deleteTag: async (id) => {
    await tagsApi.delete(id);
    set((state) => ({
      tags: state.tags.filter((t) => t.id !== id),
    }));
  },
}));
