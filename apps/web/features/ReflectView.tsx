"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Feather, MessageCircle } from "lucide-react";
import { useReflectStore } from "@/store/useReflectStore";

export const ReflectView = () => {
  const { messages, isTyping, fetchTodayMessages, sendMessage } = useReflectStore();
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetchTodayMessages();
  }, [fetchTodayMessages]);

  const aiPrompts = [
    "What was the most significant moment?",
    "How are you feeling right now?",
    "That makes complete sense. Is there anything else on your mind before we wrap up?",
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    sendMessage(inputValue);
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

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
      className="relative mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center px-4 pt-16 pb-24 sm:px-6 sm:pt-24 sm:pb-32"
    >
      <div className="mb-8 flex w-full items-center gap-4 border-b border-[var(--border-soft)] pb-6">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[var(--ink-color)] text-[var(--bg-color)] shadow-xl">
          <MessageCircle size={22} strokeWidth={1.5} />
        </div>
        <div className="flex flex-col gap-0.5">
          <h2 className="font-serif text-2xl text-[var(--ink-color)] sm:text-4xl">Reflect</h2>
          <p className="font-sans text-xs tracking-wider text-[var(--text-muted)] sm:text-sm">
            A quiet space to unpack your thoughts.
          </p>
        </div>
      </div>

      <div className="hide-scrollbar flex w-full flex-1 flex-col gap-6 overflow-y-auto pb-20">
        <AnimatePresence mode="popLayout">
          {messages.map((msg, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.5, type: "spring" }}
              className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {msg.role === "system" ? (
                <div className="flex w-full flex-col items-center justify-center gap-4 py-8">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[var(--accent-color)] text-[var(--accent-color)]">
                    <Feather size={20} />
                  </div>
                  <span className="font-serif text-lg text-[var(--ink-color)] italic sm:text-2xl">
                    {msg.content}
                  </span>
                </div>
              ) : (
                <div
                  className={`flex max-w-[85%] flex-col gap-1.5 sm:max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`relative p-4 shadow-sm sm:p-5 ${
                      msg.role === "user"
                        ? "rounded-2xl rounded-br-sm bg-[var(--ink-color)] font-sans text-sm leading-relaxed text-[var(--bg-color)]"
                        : "glass-panel font-hand rounded-2xl rounded-bl-sm border border-[var(--border-soft)] text-xl leading-snug text-[var(--ink-color)] sm:text-2xl"
                    } `}
                  >
                    {msg.role === "assistant" && (
                      <div className="absolute -bottom-2 -left-2 z-[-1] h-4 w-4 rotate-45 transform rounded-sm border border-t-0 border-r-0 border-[var(--border-soft)] bg-[var(--bg-color)]" />
                    )}
                    {msg.content}
                  </div>
                  {msg.created_at && (
                    <span className="px-1 text-[10px] tracking-wider text-[var(--text-muted)] opacity-60">
                      {new Intl.DateTimeFormat("en-US", {
                        hour: "numeric",
                        minute: "numeric",
                        hour12: true,
                      }).format(new Date(msg.created_at))}
                    </span>
                  )}
                </div>
              )}
            </motion.div>
          ))}

          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex w-full justify-start"
            >
              <div className="glass-panel flex items-center gap-1.5 rounded-2xl rounded-bl-sm border border-[var(--border-soft)] px-5 py-4">
                <motion.div
                  animate={{ y: [0, -4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0 }}
                  className="h-2 w-2 rounded-full bg-[var(--text-muted)] opacity-70"
                />
                <motion.div
                  animate={{ y: [0, -4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0.15 }}
                  className="h-2 w-2 rounded-full bg-[var(--text-muted)] opacity-70"
                />
                <motion.div
                  animate={{ y: [0, -4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.6, ease: "easeInOut", delay: 0.3 }}
                  className="h-2 w-2 rounded-full bg-[var(--text-muted)] opacity-70"
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="fixed bottom-0 left-0 z-20 flex w-full flex-col items-center gap-4 bg-gradient-to-t from-[var(--bg-color)] via-[var(--bg-color)] to-transparent px-4 pt-8 pb-4 sm:px-6 sm:pt-12 sm:pb-8"
      >
        {messages.length <= 1 && (
          <div className="flex w-full max-w-2xl flex-wrap justify-center gap-2">
            {aiPrompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => sendMessage(prompt)}
                className="glass-panel rounded-full border border-[var(--border-soft)] px-3 py-2 text-xs text-[var(--ink-color)] opacity-80 transition-opacity hover:opacity-100 sm:px-4 sm:text-sm"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
        <div className="glass-panel flex w-full max-w-2xl items-center rounded-2xl border border-[var(--border-soft)] bg-[var(--bg-color)]/80 p-1.5 shadow-lg backdrop-blur-md sm:rounded-[32px] sm:p-2">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInput}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type your response..."
            rows={1}
            className="hide-scrollbar my-2 flex-1 resize-none border-none bg-transparent px-4 font-serif text-base text-[var(--ink-color)] outline-none placeholder:text-[var(--text-muted)] placeholder:opacity-50 sm:px-6 sm:text-lg"
            style={{ maxHeight: "150px" }}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--ink-color)] text-[var(--bg-color)] transition-opacity disabled:opacity-50 sm:h-12 sm:w-12"
          >
            <Feather size={18} />
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};
