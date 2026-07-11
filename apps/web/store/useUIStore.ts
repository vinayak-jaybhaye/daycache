import { create } from "zustand";

type ViewType = "home" | "reflect" | "recall" | "calendar" | "search" | "settings";

interface UIState {
  currentView: ViewType;
  isSidebarOpen: boolean;
  setCurrentView: (view: ViewType) => void;
  setSidebarOpen: (isOpen: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  currentView: "home",
  isSidebarOpen: true,
  setCurrentView: (view) => set({ currentView: view }),
  setSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
}));
