"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Feather, Trash2 } from "lucide-react";
import { useRecallStore } from "@/store/useRecallStore";
import { useJournalStore } from "@/store/useJournalStore";
import { useRouter } from "next/navigation";
import { type RecallMessage } from "@/lib/api/ai";

const RecallMessageItem = ({
  msg,
  showDate,
  msgDate,
  suggestedQueries,
  handleQuery,
  setActiveEntry,
  deleteDayChat,
  deleteMessage,
}: {
  msg: RecallMessage;
  showDate: boolean;
  msgDate: Date;
  suggestedQueries: string[];
  handleQuery: (q: string) => void;
  setActiveEntry: (id: string) => void;
  deleteDayChat: (d: string) => void;
  deleteMessage: (id: string) => void;
}) => {
  const [showSources, setShowSources] = useState(false);
  const router = useRouter();

  return (
    <React.Fragment>
      {showDate && msg.id !== "welcome" && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="group my-4 flex w-full items-center justify-between border-b border-[var(--border-soft)] pb-2"
        >
          <span className="font-sans text-[10px] tracking-widest text-[var(--text-muted)] uppercase">
            {msgDate.toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
          <button
            onClick={() => deleteDayChat(msg.created_at.split("T")[0])}
            className="text-[var(--text-muted)] opacity-20 transition-opacity hover:text-red-500 hover:opacity-100 md:opacity-0 md:group-hover:opacity-100"
            title="Delete all messages from this day"
          >
            <Trash2 size={12} />
          </button>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`group flex w-full flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
      >
        <div
          className="flex w-full flex-col gap-1.5"
          style={{ alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}
        >
          <div
            className={`max-w-[90%] p-4 shadow-sm sm:max-w-[85%] sm:p-6 ${
              msg.role === "user"
                ? "rounded-3xl rounded-tr-sm bg-[var(--ink-color)] font-serif text-base text-[var(--bg-color)] sm:text-xl"
                : "border-none bg-transparent font-serif text-base leading-relaxed text-[var(--ink-color)] sm:text-xl"
            } `}
          >
            {msg.content}
          </div>

          {!msg.isGreeting && (
            <div
              className={`flex items-center gap-2 px-2 text-[10px] text-[var(--text-muted)] opacity-60`}
            >
              <span className="tracking-wider">
                {msgDate.toLocaleTimeString("en-US", {
                  hour: "numeric",
                  minute: "numeric",
                  hour12: true,
                })}
              </span>
              {Boolean(msg.id) && !msg.id.startsWith("temp") && (
                <button
                  onClick={() => deleteMessage(msg.id)}
                  className="text-[var(--text-muted)] opacity-20 transition-opacity hover:text-red-500 hover:opacity-100 md:opacity-0 md:group-hover:opacity-100"
                  title="Delete message"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          )}
        </div>

        {msg.isGreeting && (
          <div className="mt-6 ml-6 flex flex-wrap gap-3">
            {suggestedQueries.map((q: string, i: number) => (
              <button
                key={i}
                onClick={() => handleQuery(q)}
                className="rounded-full border border-[var(--border-soft)] px-3 py-1.5 font-sans text-xs tracking-wide text-[var(--text-muted)] transition-colors hover:bg-[var(--ink-color)] hover:text-[var(--bg-color)] sm:px-4 sm:py-2"
              >
                &quot;{q}&quot;
              </button>
            ))}
          </div>
        )}

        {msg.sources && msg.sources.length > 0 && (
          <div className="mt-4 ml-6 w-full max-w-[85%]">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1.5 font-sans text-[10px] tracking-widest text-[var(--text-muted)] uppercase transition-colors hover:text-[var(--ink-color)]"
            >
              <Feather size={10} className={showSources ? "text-[var(--accent-color)]" : ""} />
              {msg.sources ? msg.sources.length : 0}{" "}
              {msg.sources?.length === 1 ? "Source" : "Sources"} from Journal
            </button>

            <AnimatePresence>
              {showSources && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="mt-3 flex flex-col gap-2 overflow-hidden"
                >
                  {msg.sources.map((src, i: number) => (
                    <div
                      key={i}
                      onClick={() => {
                        if (src.id) {
                          setActiveEntry(src.id);
                          router.push("/journal/" + src.id);
                        }
                      }}
                      className="group/source flex cursor-pointer flex-col gap-1 rounded-xl border border-[var(--border-soft)] bg-[var(--bg-color)] p-3 shadow-sm transition-colors hover:border-[var(--accent-color)]"
                    >
                      <div className="flex items-center justify-between">
                        <p className="font-sans text-xs font-medium text-[var(--ink-color)] transition-colors group-hover/source:text-[var(--accent-color)]">
                          {src.title || src.date}
                        </p>
                        <span className="font-sans text-[9px] tracking-wider text-[var(--text-muted)] uppercase">
                          {src.date}
                        </span>
                      </div>
                      <p className="line-clamp-2 font-serif text-sm leading-relaxed text-[var(--text-muted)]">
                        &quot;{src.snippet}&quot;
                      </p>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </motion.div>
    </React.Fragment>
  );
};

export const RecallView = () => {
  const { messages, isTyping, fetchMessages, sendMessage, deleteMessage, deleteDayChat } =
    useRecallStore();
  const { setActiveEntry } = useJournalStore();
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const suggestedQueries = [
    "What was I stressed about last month?",
    "When did I first mention moving to Tokyo?",
    "How has my mood been this year?",
  ];

  const handleQuery = (queryText: string) => {
    if (!queryText.trim()) return;
    sendMessage(queryText);
    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
      className="relative mx-auto flex min-h-screen w-full max-w-4xl flex-col px-4 pt-20 pb-32 sm:px-6 sm:pt-24 md:px-12"
    >
      <div className="mb-8 flex items-center gap-4 border-b border-[var(--border-soft)] pb-6">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[var(--ink-color)] text-[var(--bg-color)] shadow-xl">
          <Search size={22} strokeWidth={1.5} />
        </div>
        <div className="flex flex-col gap-0.5">
          <h2 className="font-serif text-2xl text-[var(--ink-color)] sm:text-4xl">Recall</h2>
          <p className="font-sans text-xs tracking-wider text-[var(--text-muted)] sm:text-sm">
            Search the spaces between your memories.
          </p>
        </div>
      </div>

      <div className="hide-scrollbar flex flex-1 flex-col gap-10 overflow-y-auto pb-20">
        <AnimatePresence>
          {messages.map((msg, idx) => {
            const msgDate = msg.created_at ? new Date(msg.created_at) : new Date();
            const prevMsgDate =
              idx > 0 && messages[idx - 1].created_at
                ? new Date(messages[idx - 1].created_at).toLocaleDateString()
                : null;
            const showDate = msgDate.toLocaleDateString() !== prevMsgDate;

            return (
              <RecallMessageItem
                key={msg.id || idx}
                msg={msg}
                showDate={showDate}
                msgDate={msgDate}
                suggestedQueries={suggestedQueries}
                handleQuery={handleQuery}
                setActiveEntry={setActiveEntry}
                deleteDayChat={deleteDayChat}
                deleteMessage={deleteMessage}
              />
            );
          })}

          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-4 ml-6 flex justify-start"
            >
              <span className="animate-pulse font-serif text-[var(--text-muted)] italic">
                Searching your memories...
              </span>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      <div className="fixed bottom-0 left-0 z-20 w-full bg-gradient-to-t from-[var(--bg-color)] via-[var(--bg-color)] to-transparent px-4 pt-8 pb-4 sm:px-6 sm:pt-12 sm:pb-8 md:px-12">
        <div className="mx-auto max-w-4xl">
          <div className="glass-panel flex w-full items-center rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-color)]/80 p-1.5 shadow-lg backdrop-blur-md sm:rounded-[32px] sm:p-2">
            <Search className="ml-4 shrink-0 text-[var(--text-muted)]" size={20} />
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleInput}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleQuery(inputValue);
                }
              }}
              placeholder="Ask your journal anything..."
              rows={1}
              className="hide-scrollbar my-2 flex-1 resize-none border-none bg-transparent px-3 font-serif text-base text-[var(--ink-color)] outline-none placeholder:text-[var(--text-muted)] placeholder:opacity-50 sm:px-6 sm:text-lg"
              style={{ maxHeight: "150px" }}
            />
            <button
              onClick={() => handleQuery(inputValue)}
              disabled={!inputValue.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--ink-color)] text-[var(--bg-color)] transition-opacity disabled:opacity-50 sm:h-12 sm:w-12"
            >
              <Feather size={18} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
