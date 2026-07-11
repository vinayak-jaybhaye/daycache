"use client";

import React from "react";
import { motion } from "framer-motion";
import type { JournalEntryResponse } from "@/lib/api/entries";

interface CardProps {
  entry: JournalEntryResponse;
  onClick?: () => void;
}

export const JournalCard = ({ entry, onClick }: CardProps) => (
  <motion.div
    whileTap={{ scale: 0.98 }}
    onClick={onClick}
    className="paper-card group relative mb-8 cursor-pointer overflow-hidden rounded-sm p-8 transition-transform duration-300 lg:hover:-translate-y-1 lg:hover:scale-[1.01]"
  >
    <div className="absolute top-0 left-0 h-full w-1 bg-[var(--accent-color)] opacity-30 transition-opacity lg:group-hover:opacity-100" />
    <span className="mb-4 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
      {new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(
        new Date(entry.date + "T12:00:00Z"),
      )}
    </span>
    {entry.title && (
      <h3 className="mb-3 font-serif text-2xl text-[var(--ink-color)]">{entry.title}</h3>
    )}
    <p className="line-clamp-3 font-serif leading-relaxed text-[var(--text-muted)]">
      {entry.content_text || ""}
    </p>
    <div className="mt-6 flex flex-wrap gap-2">
      {entry.tags?.map((tag: { id: string; name: string }) => (
        <span key={tag.id} className="font-hand text-lg text-[var(--accent-color)]">
          #{tag.name}
        </span>
      ))}
    </div>
  </motion.div>
);

export const PolaroidCard = ({ entry, onClick }: CardProps) => {
  const imageUrl = entry.media?.[0]?.read_url || "https://via.placeholder.com/600";

  return (
    <motion.div
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="paper-card mb-8 cursor-pointer rounded-sm bg-white p-4 pb-12 shadow-xl transition-transform duration-300 lg:hover:-translate-y-2 lg:hover:rotate-2"
      style={{ rotate: "-2deg" }}
    >
      <div className="mb-4 aspect-square w-full overflow-hidden rounded-sm bg-gray-200">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt="Polaroid"
          className="h-full w-full object-cover grayscale-[20%] sepia-[10%]"
        />
      </div>
      <p className="font-hand text-center text-2xl text-[var(--ink-color)]">{entry.content_text}</p>
    </motion.div>
  );
};

export const StickyNote = ({ entry, onClick }: CardProps) => (
  <motion.div
    whileTap={{ scale: 0.98 }}
    onClick={onClick}
    className="relative mb-8 w-64 cursor-pointer p-6 shadow-md transition-transform duration-300 lg:hover:scale-105 lg:hover:-rotate-2"
    style={{ backgroundColor: "#FDE68A", rotate: "3deg" }}
  >
    <div className="absolute -top-3 left-1/2 h-4 w-12 -translate-x-1/2 rotate-1 bg-white/40 shadow-sm backdrop-blur-sm" />
    <span className="mb-2 block font-sans text-[10px] tracking-widest text-black/40 uppercase">
      {new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(
        new Date(entry.date + "T12:00:00Z"),
      )}
    </span>
    <p className="font-hand text-2xl leading-snug text-black/80">{entry.content_text}</p>
  </motion.div>
);
