import { create } from "zustand";
import { recallApi, type RecallMessage } from "@/lib/api/ai";
import { isAxiosError } from "axios";

interface RecallState {
  messages: RecallMessage[];
  isLoading: boolean;
  isTyping: boolean;
  error: string | null;

  fetchMessages: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  deleteDayChat: (dateVal: string) => Promise<void>;
}

export const useRecallStore = create<RecallState>((set, get) => ({
  messages: [],
  isLoading: false,
  isTyping: false,
  error: null,

  fetchMessages: async () => {
    set({ isLoading: true, error: null });
    try {
      const messages = await recallApi.listMessages();
      if (!messages || messages.length === 0) {
        set({
          messages: [
            {
              role: "assistant",
              content: "I remember everything you've written here. What would you like to recall?",
              id: "welcome",
              created_at: new Date().toISOString(),
              isGreeting: true,
            } as RecallMessage,
          ],
          isLoading: false,
        });
      } else {
        const mapped = messages.map((m, idx: number) => ({
          ...m,
          isGreeting: idx === 0 && m.role === "assistant",
          sources: m.retrieved_entries?.map((entry) => ({
            id: entry.entry_id,
            date: entry.day_date,
            title: entry.entry_title,
            snippet: entry.snippet || entry.entry_title || "Journal entry",
          })),
        }));
        set({ messages: mapped, isLoading: false });
      }
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 404) {
        set({
          messages: [
            {
              role: "assistant",
              content: "I remember everything you've written here. What would you like to recall?",
              id: "welcome",
              created_at: new Date().toISOString(),
              isGreeting: true,
            } as RecallMessage,
          ],
          isLoading: false,
        });
      } else {
        set({ isLoading: false, error: "Failed to fetch messages" });
      }
    }
  },

  sendMessage: async (content) => {
    // Optimistic UI update
    const userMsg = {
      id: "temp",
      created_at: new Date().toISOString(),
      role: "user",
      content,
    } as RecallMessage;
    set((state) => ({
      messages: [...state.messages, userMsg],
      isTyping: true,
    }));

    try {
      const response = await recallApi.sendMessage({ content });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body?.getReader() || null;
      const decoder = new TextDecoder();
      let aiMsgContent = "";

      if (!reader) {
        // Handle non-stream response (fallback)
        const data = await response.json().catch(() => ({}));
        const assistantMsg = {
          id: `ai-${Date.now()}`,
          created_at: new Date().toISOString(),
          role: "assistant" as const,
          content: data.content || "I understand.",
        } as RecallMessage;
        set((state) => ({
          messages: [...state.messages, assistantMsg],
        }));
        return;
      }

      // Add empty AI message
      set((state) => ({
        messages: [
          ...state.messages,
          {
            id: "ai",
            created_at: new Date().toISOString(),
            role: "assistant",
            content: "",
          } as RecallMessage,
        ],
      }));

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") break;

            if (data.startsWith("{")) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.error) {
                  set({ error: parsed.error });
                }
              } catch {
                // Ignore parse errors on incomplete chunks
              }
            } else {
              aiMsgContent += data;
              set((state) => {
                const newMessages = [...state.messages];
                newMessages[newMessages.length - 1].content = aiMsgContent;
                return { messages: newMessages };
              });
            }
          }
        }
      }

      // Refresh messages from server to retrieve sources metadata
      await get().fetchMessages();
    } catch (err: unknown) {
      console.error(err);
      set({ error: "Failed to send message" });
    } finally {
      set({ isTyping: false });
    }
  },

  deleteMessage: async (messageId: string) => {
    try {
      await recallApi.deleteMessage(messageId);
      // Remove the message and its immediate assistant reply (since the API deletes paired messages)
      set((state) => {
        const msgIndex = state.messages.findIndex((m) => m.id === messageId);
        if (msgIndex === -1) return state;
        const newMessages = [...state.messages];
        newMessages.splice(msgIndex, 1);
        // If the next message is an assistant reply, remove it too
        if (msgIndex < newMessages.length && newMessages[msgIndex].role === "assistant") {
          newMessages.splice(msgIndex, 1);
        }
        return { messages: newMessages };
      });
    } catch (err) {
      console.error("Failed to delete message", err);
    }
  },

  deleteDayChat: async (dateVal: string) => {
    try {
      await recallApi.deleteMessagesByDate(dateVal);
      // Remove all messages matching this date from state
      set((state) => ({
        messages: state.messages.filter((m) => m.created_at && !m.created_at.startsWith(dateVal)),
      }));
    } catch (err) {
      console.error("Failed to delete day chat", err);
    }
  },
}));
