"use client";

import React, { useEffect } from "react";
import { useParams } from "next/navigation";
import { EditorView } from "@/features/editor/EditorView";
import { useJournalStore } from "@/store/useJournalStore";
import { motion } from "framer-motion";

export default function JournalPage() {
  const params = useParams();
  const id = params?.id as string;
  const { setActiveEntry, fetchEntry } = useJournalStore();

  useEffect(() => {
    if (id) {
      const currentEntries = useJournalStore.getState().entries;
      if (id !== "new" && !currentEntries[id]) {
        fetchEntry(id);
      }
      setActiveEntry(id);
    }
    // Cleanup active entry on unmount
    return () => setActiveEntry(null);
  }, [id, setActiveEntry, fetchEntry]);

  return (
    <motion.div
      key="editor"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      className="hide-scrollbar absolute inset-0 z-10 h-full w-full overflow-y-auto bg-[var(--bg-color)]"
    >
      <EditorView />
    </motion.div>
  );
}
