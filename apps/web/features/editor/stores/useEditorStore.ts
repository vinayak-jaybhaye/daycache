/**
 * useEditorStore — UI state management for the editor.
 *
 * Tracks UI-only state (focus, mode, selection) separate from document content.
 * This keeps the main editor store clean and document-focused.
 */

import { create } from "zustand";
import type { EditorUIState } from "../types";

interface EditorStoreState extends EditorUIState {
  setFocused: (focused: boolean) => void;
  setEditMode: (mode: "edit" | "view") => void;
  setSelectedText: (text: string) => void;
  setCursorPos: (pos: number) => void;
  reset: () => void;
}

/**
 * Initial state for editor UI.
 */
const initialState: EditorUIState = {
  isFocused: false,
  editMode: "edit",
  selectedText: "",
  cursorPos: 0,
};

/**
 * Store for editor UI state.
 * Separate from document content and upload state.
 */
export const useEditorStore = create<EditorStoreState>((set) => ({
  ...initialState,

  setFocused: (focused: boolean) => {
    set({ isFocused: focused });
  },

  setEditMode: (mode: "edit" | "view") => {
    set({ editMode: mode });
  },

  setSelectedText: (text: string) => {
    set({ selectedText: text });
  },

  setCursorPos: (pos: number) => {
    set({ cursorPos: pos });
  },

  reset: () => {
    set(initialState);
  },
}));
