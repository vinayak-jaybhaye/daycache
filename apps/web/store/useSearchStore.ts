import { create } from "zustand";
import { searchApi, type SearchResult } from "@/lib/api/search";

interface SearchState {
  results: SearchResult[];
  query: string;
  isSearching: boolean;
  nextCursor: string | null;

  setQuery: (q: string) => void;
  executeSearch: () => Promise<void>;
  fetchMoreResults: () => Promise<void>;
  clearResults: () => void;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  results: [],
  query: "",
  isSearching: false,
  nextCursor: null,

  setQuery: (q) => set({ query: q }),

  clearResults: () => set({ results: [], query: "", isSearching: false, nextCursor: null }),

  executeSearch: async () => {
    const { query } = get();
    if (!query.trim()) {
      set({ results: [], isSearching: false, nextCursor: null });
      return;
    }

    set({ isSearching: true });
    try {
      const results = await searchApi.search({ q: query, skip: 0, limit: 20 });
      set({
        results: results || [],
        nextCursor: results.length === 20 ? "has_more" : null,
        isSearching: false,
      });
    } catch (err) {
      console.error("Search failed", err);
      set({ results: [], nextCursor: null, isSearching: false });
    }
  },

  fetchMoreResults: async () => {
    const { query, nextCursor, isSearching, results } = get();
    if (!query.trim() || !nextCursor || isSearching) return;

    set({ isSearching: true });
    try {
      const moreResults = await searchApi.search({ q: query, skip: results.length, limit: 20 });
      set({
        results: [...results, ...(moreResults || [])],
        nextCursor: moreResults.length === 20 ? "has_more" : null,
        isSearching: false,
      });
    } catch (err) {
      console.error("Search fetch more failed", err);
      set({ isSearching: false });
    }
  },
}));
