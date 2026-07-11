"use client";

import React from "react";
import { motion } from "framer-motion";
import { useJournalStore } from "@/store/useJournalStore";
import { JournalCard, PolaroidCard, StickyNote } from "@/components/Cards";
import { DoodleStar } from "@/components/Doodles";
import { useRouter } from "next/navigation";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";

export const TimelineView = () => {
  const { entries, timeline, days, fetchDays, fetchEntries, nextCursor, isLoading } =
    useJournalStore();
  const router = useRouter();

  const { loadMoreRef } = useInfiniteScroll({
    onLoadMore: () => fetchEntries(false),
    hasMore: !!nextCursor,
    isLoading,
  });

  React.useEffect(() => {
    // Fetch days for the current month
    const today = new Date();
    const startDate = new Date(today.getFullYear(), today.getMonth(), 1)
      .toISOString()
      .split("T")[0];
    const endDate = new Date(today.getFullYear(), today.getMonth() + 1, 0)
      .toISOString()
      .split("T")[0];
    fetchDays(startDate, endDate);
  }, [fetchDays]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.8 }}
      className="relative mx-auto min-h-screen w-full max-w-4xl px-4 pt-20 pb-32 sm:px-6 sm:pt-24 sm:pb-48"
    >
      <div className="mb-16 text-center">
        <h2 className="mb-4 font-serif text-3xl text-[var(--ink-color)] sm:text-4xl md:text-5xl">
          Memory Timeline
        </h2>
        <p className="font-sans text-sm tracking-widest text-[var(--text-muted)] uppercase">
          October 2026
        </p>
      </div>

      <div className="absolute top-48 bottom-48 left-1/2 z-0 hidden w-px -translate-x-1/2 bg-[var(--border-soft)] md:block"></div>

      <div className="relative z-10 flex flex-col gap-16 md:gap-24">
        {timeline.map((id, index) => {
          const entry = entries[id];
          if (!entry) return null;

          const entryDateObj = new Date(entry.date + "T12:00:00Z");

          return (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className={`flex w-full flex-col items-center gap-8 md:flex-row md:gap-16 ${index % 2 === 0 ? "md:flex-row" : "md:flex-row-reverse"}`}
            >
              {/* Date & Metadata */}
              <div
                className={`flex w-full flex-col md:w-1/2 ${index % 2 === 0 ? "md:items-end md:text-right" : "md:items-start md:text-left"} items-center`}
              >
                <span className="font-hand mb-2 text-2xl text-[var(--ink-color)] sm:text-3xl">
                  {new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric" }).format(
                    entryDateObj,
                  )}
                </span>
                <div className="flex flex-wrap items-center justify-center gap-3 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                  {entry.moods && entry.moods.length > 0 && (
                    <span className="flex items-center gap-1">
                      <span
                        className="h-2 w-2 rounded-full opacity-70"
                        style={{ backgroundColor: entry.moods[0].color }}
                      ></span>
                      {entry.moods[0].name}
                    </span>
                  )}
                  {entry.date && days[entry.date]?.location?.name && (
                    <span>• {days[entry.date]?.location?.name}</span>
                  )}
                  {entry.date && days[entry.date]?.weather?.condition && (
                    <span>• {days[entry.date]?.weather?.condition}</span>
                  )}
                  <span>• {entry.word_count} words</span>
                </div>
              </div>

              {/* Timeline Node */}
              <div className="relative hidden h-8 w-8 items-center justify-center md:flex">
                <div className="absolute z-10 h-3 w-3 rounded-full border-2 border-[var(--accent-color)] bg-[var(--bg-color)]"></div>
                <DoodleStar className="absolute -top-4 -right-6 scale-50 rotate-45 text-[var(--ink-color)] opacity-40" />
              </div>

              {/* Entry Card Preview */}
              <div className="flex w-full justify-center md:w-1/2 md:justify-start">
                <div className="w-full max-w-sm origin-center scale-90 transform transition-transform duration-500 hover:scale-100">
                  {(() => {
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

                    if (uiType === "polaroid") {
                      return (
                        <PolaroidCard
                          entry={entry}
                          onClick={() => router.push(`/journal/${entry.id}`)}
                        />
                      );
                    } else if (uiType === "sticky") {
                      return (
                        <StickyNote
                          entry={entry}
                          onClick={() => router.push(`/journal/${entry.id}`)}
                        />
                      );
                    } else {
                      return (
                        <JournalCard
                          entry={entry}
                          onClick={() => router.push(`/journal/${entry.id}`)}
                        />
                      );
                    }
                  })()}
                </div>
              </div>
            </motion.div>
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
