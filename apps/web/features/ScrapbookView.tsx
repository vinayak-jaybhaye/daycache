"use client";

import React from "react";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { useJournalStore } from "@/store/useJournalStore";
import { JournalCard, PolaroidCard, StickyNote } from "@/components/Cards";
import { useRouter } from "next/navigation";

import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";

export const ScrapbookView = ({
  title = "DayCache",
  description = "Every memory deserves a beautiful place.",
  icon = undefined,
  onEdit = undefined,
}: {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  onEdit?: () => void;
}) => {
  const { entries, timeline, fetchEntries, nextCursor, isLoading } = useJournalStore();
  const router = useRouter();

  const { loadMoreRef } = useInfiniteScroll({
    onLoadMore: () => fetchEntries(false),
    hasMore: !!nextCursor,
    isLoading,
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
      className="relative min-h-screen w-full px-4 pt-16 pb-32 sm:px-6 sm:pt-24 sm:pb-48 md:px-12 lg:px-24"
    >
      <div className="mb-8 flex flex-col gap-4 sm:mb-16 sm:flex-row sm:items-end sm:justify-between">
        <div className="group flex min-w-0 items-center gap-3 sm:gap-4">
          {icon}
          <div className="min-w-0">
            <div className="flex items-center gap-2 sm:gap-4">
              <h1 className="mb-2 font-serif text-3xl text-[var(--ink-color)] sm:mb-4 sm:text-4xl md:text-6xl">
                {title}
              </h1>
              {onEdit && (
                <button
                  onClick={onEdit}
                  className="mb-2 shrink-0 rounded-full p-2 text-[var(--text-muted)] opacity-0 transition-all group-hover:opacity-100 hover:bg-[var(--surface-elevated)] hover:text-[var(--ink-color)]"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                    <path d="m15 5 4 4" />
                  </svg>
                </button>
              )}
            </div>
            <p className="font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase sm:text-sm">
              {description}
            </p>
          </div>
        </div>
        <button
          onClick={() => router.push("/journal/new")}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--ink-color)] text-[var(--bg-color)] shadow-xl transition-transform hover:scale-105 sm:h-14 sm:w-14"
        >
          <Plus size={22} />
        </button>
      </div>

      <div className="relative z-10 columns-1 gap-4 space-y-4 sm:gap-8 sm:space-y-8 md:columns-2 lg:columns-3">
        {timeline.map((id) => {
          const entry = entries[id];
          if (!entry) return null;
          // Parse content if it's a string
          let contentObj: Record<string, unknown> = {};
          try {
            if (typeof entry.content === "string") {
              contentObj = JSON.parse(entry.content);
            } else if (entry.content) {
              contentObj = entry.content;
            }
          } catch {
            contentObj = {};
          }

          const uiType = contentObj?.ui_type || "journal";

          return (
            <div key={entry.id} className="break-inside-avoid">
              {uiType === "journal" && (
                <JournalCard entry={entry} onClick={() => router.push(`/journal/${entry.id}`)} />
              )}
              {uiType === "polaroid" && (
                <PolaroidCard entry={entry} onClick={() => router.push(`/journal/${entry.id}`)} />
              )}
              {uiType === "sticky" && (
                <div className="flex justify-center py-8">
                  <StickyNote entry={entry} onClick={() => router.push(`/journal/${entry.id}`)} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {nextCursor && (
        <div ref={loadMoreRef} className="mt-16 flex justify-center pb-8">
          {isLoading ? (
            <div className="font-sans text-sm tracking-widest text-[var(--text-muted)] uppercase">
              Loading...
            </div>
          ) : (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-soft)] border-t-[var(--ink-color)]"></div>
          )}
        </div>
      )}
    </motion.div>
  );
};
