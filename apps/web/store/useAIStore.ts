import { create } from "zustand";
import { aiApi, SummaryResponse } from "@/lib/api/ai";

interface AIState {
  summaries: Record<string, SummaryResponse>; // key: id or scope-date combo
  isLoading: boolean;

  getSummaryForEntry: (entryId: string) => Promise<SummaryResponse | null>;
  getSummaryForDay: (dateStr: string) => Promise<SummaryResponse | null>;
  getSummaryForWeek: (dateStr: string) => Promise<SummaryResponse | null>;
  getSummaryForMonth: (year: number, month: number) => Promise<SummaryResponse | null>;
  getSummaryForYear: (year: number) => Promise<SummaryResponse | null>;
}

export const useAIStore = create<AIState>((set) => ({
  summaries: {},
  isLoading: false,

  getSummaryForEntry: async (entryId) => {
    try {
      const summary = await aiApi.generateEntrySummary(entryId);
      set((state) => ({ summaries: { ...state.summaries, [`entry-${entryId}`]: summary } }));
      return summary;
    } catch {
      return null;
    }
  },

  getSummaryForDay: async (dateStr) => {
    try {
      const summary = await aiApi.generateDaySummary(dateStr);
      set((state) => ({ summaries: { ...state.summaries, [`day-${dateStr}`]: summary } }));
      return summary;
    } catch {
      return null;
    }
  },

  getSummaryForWeek: async (dateStr) => {
    try {
      const summary = await aiApi.generateWeeklySummary(dateStr);
      set((state) => ({ summaries: { ...state.summaries, [`week-${dateStr}`]: summary } }));
      return summary;
    } catch {
      return null;
    }
  },

  getSummaryForMonth: async (year, month) => {
    try {
      const summary = await aiApi.generateMonthlySummary(year, month);
      set((state) => ({ summaries: { ...state.summaries, [`month-${year}-${month}`]: summary } }));
      return summary;
    } catch {
      return null;
    }
  },

  getSummaryForYear: async (year) => {
    try {
      const summary = await aiApi.generateYearlySummary(year);
      set((state) => ({ summaries: { ...state.summaries, [`year-${year}`]: summary } }));
      return summary;
    } catch {
      return null;
    }
  },
}));
