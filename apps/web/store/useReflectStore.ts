import { create } from "zustand";
import { reflectApi, type ReflectMessage } from "@/lib/api/ai";
import { isAxiosError } from "axios";

interface ReflectState {
  messages: ReflectMessage[];
  isLoading: boolean;
  isTyping: boolean;
  error: string | null;

  fetchTodayMessages: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
}

export const useReflectStore = create<ReflectState>((set) => ({
  messages: [],
  isLoading: false,
  isTyping: false,
  error: null,

  fetchTodayMessages: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await reflectApi.listTodayMessages();
      const messages = Array.isArray(response)
        ? response
        : (response as { messages?: ReflectMessage[] }).messages || [];
      set({ messages, isLoading: false });
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 404) {
        set({
          messages: [
            {
              id: "ai",
              created_at: new Date().toISOString(),
              date: new Date().toISOString().split("T")[0],
              role: "assistant",
              content: "Hi there. How did today go?",
            } as ReflectMessage,
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
      date: new Date().toISOString().split("T")[0],
      role: "user",
      content,
    } as ReflectMessage;
    set((state) => ({
      messages: [...state.messages, userMsg],
      isTyping: true,
    }));

    try {
      const response = await reflectApi.sendMessage({ content });

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
        } as ReflectMessage;
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
            date: new Date().toISOString().split("T")[0],
            role: "assistant",
            content: "",
          } as ReflectMessage,
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
                // Ignore parse error on incomplete chunks
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
    } catch (err: unknown) {
      console.error(err);
      set({ error: "Failed to send message" });
    } finally {
      set({ isTyping: false });
    }
  },
}));
