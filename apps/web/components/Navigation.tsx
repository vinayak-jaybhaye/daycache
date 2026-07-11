"use client";

import React from "react";
import { motion } from "framer-motion";
import { Home, Calendar, Feather, MessageCircle, Search, Settings } from "lucide-react";
import { useUIStore } from "@/store/useUIStore";

export const Navigation = () => {
  const { currentView, setCurrentView } = useUIStore();

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="fixed bottom-8 left-1/2 z-50 -translate-x-1/2"
    >
      <div className="glass-panel flex items-center gap-4 rounded-full border border-[var(--border-soft)] px-4 py-3 shadow-2xl sm:gap-8 sm:px-6 sm:py-4">
        {[
          { id: "home", icon: Home, label: "Scrapbook" },
          { id: "calendar", icon: Calendar, label: "Timeline" },
          { id: "reflect", icon: Feather, label: "Reflect" },
          { id: "recall", icon: MessageCircle, label: "Recall" },
          { id: "search", icon: Search, label: "Search" },
          { id: "settings", icon: Settings, label: "Settings" },
        ].map(({ id, icon: Icon, label }) => {
          const isActive = currentView === id;
          return (
            <button
              key={id}
              onClick={() =>
                setCurrentView(
                  id as "home" | "calendar" | "reflect" | "recall" | "search" | "settings",
                )
              }
              title={label}
              className={`relative flex flex-col items-center gap-1 transition-colors ${isActive ? "text-[var(--ink-color)]" : "text-[var(--text-muted)] hover:text-[var(--ink-color)]"}`}
            >
              <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
              {isActive && (
                <motion.div
                  layoutId="dock-indicator"
                  className="absolute -bottom-3 h-1 w-1 rounded-full bg-[var(--ink-color)]"
                />
              )}
            </button>
          );
        })}
      </div>
    </motion.div>
  );
};
