"use client";

import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search } from "lucide-react";
import { DoodleStar, DoodleArrow } from "@/components/Doodles";
import { useSearchStore } from "@/store/useSearchStore";
import { useCollectionStore } from "@/store/useCollectionStore";
import { useRouter } from "next/navigation";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";

export const SearchView = () => {
  const { query, setQuery, results, isSearching, executeSearch, nextCursor, fetchMoreResults } =
    useSearchStore();
  const { collections, fetchCollections } = useCollectionStore();
  const router = useRouter();

  const { loadMoreRef } = useInfiniteScroll({
    onLoadMore: fetchMoreResults,
    hasMore: !!nextCursor,
    isLoading: isSearching,
  });

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  useEffect(() => {
    const handler = setTimeout(() => {
      executeSearch();
    }, 500);
    return () => clearTimeout(handler);
  }, [query, executeSearch]);

  const handleResultClick = (id: string) => {
    router.push(`/journal/${id}`);
  };
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
      className="relative flex h-screen w-full flex-col items-center overflow-hidden px-4 pt-8 sm:px-6 sm:pt-12 md:px-12"
    >
      <DoodleStar className="absolute top-40 left-[10%] scale-150 text-[var(--ink-color)] opacity-20" />
      <DoodleArrow className="absolute right-[10%] bottom-60 rotate-90 text-[var(--ink-color)] opacity-20" />

      <motion.div
        initial={{ y: -20, scale: 0.95 }}
        animate={{ y: 0, scale: 1 }}
        className="glass-panel relative z-30 mb-8 flex w-full max-w-3xl shrink-0 items-center gap-4 rounded-3xl border border-[var(--border-soft)] p-4 shadow-2xl md:p-6"
      >
        <Search className="ml-4 shrink-0 text-[var(--accent-color)]" size={32} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by feeling, place, or memory..."
          className="w-full border-none bg-transparent font-serif text-xl text-[var(--ink-color)] outline-none placeholder:text-[var(--text-muted)] placeholder:opacity-40 sm:text-2xl md:text-4xl"
          autoFocus
        />
      </motion.div>

      {/* Scrollable Content Area */}
      <div className="hide-scrollbar z-20 flex w-full flex-1 flex-col items-center overflow-y-auto px-2 pt-4 pb-32">
        {/* Suggested Tags (hide if searching) */}
        <AnimatePresence>
          {!query && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mb-16 flex w-full max-w-4xl flex-wrap justify-center gap-2 sm:mb-24 sm:gap-4"
            >
              {[
                "Reflective",
                "Kyoto trips",
                "Photos from Autumn",
                "Design notes",
                "Coffee shops",
              ].map((tag, i) => (
                <button
                  key={i}
                  onClick={() => setQuery(tag)}
                  className="cursor-pointer rounded-full border border-[var(--border-soft)] px-3 py-1.5 font-sans text-xs tracking-wide text-[var(--text-muted)] backdrop-blur-md transition-colors sm:px-5 sm:py-2 sm:text-sm lg:hover:border-[var(--ink-color)] lg:hover:bg-[var(--ink-color)] lg:hover:text-[var(--bg-color)]"
                >
                  {tag}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Results */}
        {query && (
          <div className="flex w-full max-w-4xl flex-col gap-6">
            {isSearching ? (
              <div className="animate-pulse text-center font-serif text-[var(--text-muted)] italic">
                Searching...
              </div>
            ) : results.length > 0 ? (
              results.map((item) => {
                const entry = item.entry;
                if (!entry) return null;

                return (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={entry.id}
                    onClick={() => handleResultClick(entry.id)}
                    className="glass-panel cursor-pointer rounded-2xl border border-[var(--border-soft)] p-6 transition-colors lg:hover:border-[var(--ink-color)]"
                  >
                    <div className="mb-2 flex flex-col gap-1 sm:flex-row sm:justify-between">
                      <h4 className="font-serif text-lg text-[var(--ink-color)] sm:text-2xl">
                        {entry.title || "Untitled Entry"}
                      </h4>
                      <span className="shrink-0 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                        {item.day_date || entry.date}
                      </span>
                    </div>
                    <p className="line-clamp-2 font-serif text-base leading-relaxed text-[var(--text-muted)] sm:text-lg">
                      {item.highlight_snippet || (entry.content_text || "").substring(0, 150)}
                    </p>
                  </motion.div>
                );
              })
            ) : (
              <div className="text-center font-serif text-[var(--text-muted)] italic">
                No memories found.
              </div>
            )}

            {nextCursor && (
              <div ref={loadMoreRef} className="mt-8 flex justify-center pb-8">
                {isSearching ? (
                  <div className="font-sans text-sm tracking-widest text-[var(--text-muted)] uppercase">
                    Loading...
                  </div>
                ) : (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--border-soft)] border-t-[var(--ink-color)]"></div>
                )}
              </div>
            )}
          </div>
        )}

        {!query && (
          <div className="mt-auto w-full max-w-6xl pb-16">
            <h3 className="mb-6 border-l-2 border-[var(--accent-color)] pl-4 font-serif text-2xl text-[var(--ink-color)] sm:mb-8 sm:text-3xl">
              Your Collections
            </h3>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-6 md:grid-cols-4 lg:grid-cols-5">
              {Object.values(collections).length > 0 ? (
                Object.values(collections).map((col, i) => (
                  <motion.div
                    key={col.id}
                    onClick={() => router.push(`/collection/${col.id}`)}
                    className={`paper-card group relative flex aspect-[3/4] cursor-pointer flex-col justify-end overflow-hidden p-4 shadow-lg transition-all duration-500 hover:shadow-2xl sm:p-6 lg:hover:-translate-y-2 ${i % 2 === 0 ? "lg:hover:rotate-2" : "lg:hover:-rotate-2"}`}
                    style={{ borderLeft: `12px solid ${"#8B9BB4"}` }}
                  >
                    <div className="absolute inset-0 z-10 bg-gradient-to-t from-black/40 to-transparent opacity-0 transition-opacity lg:group-hover:opacity-100" />
                    <div className="relative z-20">
                      <span className="mb-1 block font-sans text-[10px] tracking-widest text-[var(--text-muted)] uppercase transition-colors sm:mb-2 sm:text-xs lg:group-hover:text-white">
                        {"Collection"}
                      </span>
                      <h4 className="font-serif text-lg leading-tight text-[var(--ink-color)] transition-colors sm:text-2xl lg:group-hover:text-white">
                        {col.name}
                      </h4>
                    </div>
                  </motion.div>
                ))
              ) : (
                <div className="col-span-full py-8 text-center font-serif text-[var(--text-muted)] italic">
                  No collections yet.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
};
