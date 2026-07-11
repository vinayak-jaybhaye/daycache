"use client";

import React, { useEffect } from "react";
import { useParams } from "next/navigation";
import { ScrapbookView } from "@/features/ScrapbookView";
import { useJournalStore } from "@/store/useJournalStore";
import { useCollectionStore } from "@/store/useCollectionStore";
import { X } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function CollectionPage() {
  const params = useParams();
  const id = params?.id as string;
  const { setFilter } = useJournalStore();
  const { collections, updateCollection } = useCollectionStore();

  const collection = collections[id];

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const handleEditClick = () => {
    if (collection) {
      setEditName(collection.name);
      setEditDesc(collection.description || "");
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (collection) {
      await updateCollection(collection.id, {
        name: editName,
        description: editDesc,
      });
      setIsEditing(false);
    }
  };

  useEffect(() => {
    if (id) {
      setFilter({ type: "collection", id });
    }
  }, [id, setFilter]);

  if (!collection) {
    return <ScrapbookView title="Collection not found" description="" />;
  }

  return (
    <>
      <ScrapbookView
        title={collection.name}
        description={collection.description || "Collection of memories."}
        onEdit={handleEditClick}
      />

      <AnimatePresence>
        {isEditing && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
              onClick={() => setIsEditing(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed top-1/2 left-1/2 z-50 flex w-full max-w-md -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-2xl border border-[var(--border-soft)] bg-[var(--surface-sunken)] p-6 shadow-2xl"
            >
              <div className="mb-2 flex items-center justify-between">
                <h2 className="font-serif text-xl text-[var(--ink-color)]">Edit Collection</h2>
                <button
                  onClick={() => setIsEditing(false)}
                  className="text-[var(--text-muted)] hover:text-[var(--ink-color)]"
                >
                  <X size={20} />
                </button>
              </div>

              <div>
                <label className="mb-2 block text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">
                  Name
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border-soft)] bg-[var(--surface-elevated)] px-4 py-2 text-sm text-[var(--ink-color)] outline-none focus:border-[var(--ink-color)]"
                />
              </div>

              <div>
                <label className="mb-2 block text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">
                  Description
                </label>
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  rows={3}
                  className="w-full resize-none rounded-lg border border-[var(--border-soft)] bg-[var(--surface-elevated)] px-4 py-2 text-sm text-[var(--ink-color)] outline-none focus:border-[var(--ink-color)]"
                  placeholder="What is this collection about?"
                />
              </div>

              <div className="mt-4 flex justify-end gap-3">
                <button
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-elevated)]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="rounded-lg bg-[var(--ink-color)] px-4 py-2 text-sm font-medium text-[var(--bg-color)] shadow-md transition-transform hover:scale-105"
                >
                  Save Changes
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
