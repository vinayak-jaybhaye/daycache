import { create } from "zustand";
import { collectionsApi, type CollectionResponse } from "@/lib/api/collections";
import type { JournalEntryResponse } from "@/lib/api/entries";

interface CollectionState {
  collections: Record<string, CollectionResponse>;
  collectionEntries: Record<string, JournalEntryResponse[]>;
  isLoading: boolean;

  fetchCollections: () => Promise<void>;
  createCollection: (name: string, description?: string) => Promise<void>;
  updateCollection: (id: string, updates: Partial<CollectionResponse>) => Promise<void>;
  deleteCollection: (id: string) => Promise<void>;

  fetchCollectionEntries: (id: string) => Promise<void>;
  addEntryToCollection: (collectionId: string, entryId: string) => Promise<void>;
  removeEntryFromCollection: (collectionId: string, entryId: string) => Promise<void>;
}

export const useCollectionStore = create<CollectionState>((set, get) => ({
  collections: {},
  collectionEntries: {},
  isLoading: false,

  fetchCollections: async () => {
    set({ isLoading: true });
    try {
      const collectionsList = await collectionsApi.list();
      const collectionsMap: Record<string, CollectionResponse> = {};
      (collectionsList || []).forEach((c) => {
        collectionsMap[c.id] = c;
      });
      set({ collections: collectionsMap, isLoading: false });
    } catch (error) {
      console.error("Failed to fetch collections", error);
      set({ isLoading: false });
    }
  },

  createCollection: async (name, description) => {
    const newCollection = await collectionsApi.create({ name, description });
    set((state) => ({
      collections: { ...state.collections, [newCollection.id]: newCollection },
    }));
  },

  updateCollection: async (id, updates) => {
    const updated = await collectionsApi.update(id, updates);
    set((state) => ({
      collections: { ...state.collections, [id]: updated },
    }));
  },

  deleteCollection: async (id) => {
    await collectionsApi.delete(id);
    set((state) => {
      const newCols = { ...state.collections };
      delete newCols[id];
      return { collections: newCols };
    });
  },

  fetchCollectionEntries: async (id) => {
    try {
      // Use entriesApi directly since backend no longer has a dedicated endpoint for this
      const { entriesApi } = await import("@/lib/api/entries");
      const data = await entriesApi.list({ collection_id: id });
      set((state) => ({
        collectionEntries: { ...state.collectionEntries, [id]: data?.items || [] },
      }));
    } catch (error) {
      console.error("Failed to fetch collection entries", error);
    }
  },

  addEntryToCollection: async (collectionId, entryId) => {
    await collectionsApi.addEntry(collectionId, entryId);
    await get().fetchCollections(); // Refresh count
  },

  removeEntryFromCollection: async (collectionId, entryId) => {
    await collectionsApi.removeEntry(collectionId, entryId);
    await get().fetchCollections(); // Refresh count

    set((state) => ({
      collectionEntries: {
        ...state.collectionEntries,
        [collectionId]: (state.collectionEntries[collectionId] || []).filter(
          (e) => e.id !== entryId,
        ),
      },
    }));
  },
}));
