"use client";

import React, { useState, useEffect, useRef } from "react";
import { Star, Tag, Folder, Plus, X, Sparkles, Loader2 } from "lucide-react";
import { useJournalStore } from "@/store/useJournalStore";
import { useTagStore } from "@/store/useTagStore";
import { useCollectionStore } from "@/store/useCollectionStore";
import { useAIStore } from "@/store/useAIStore";
import { useOnClickOutside } from "@/hooks/useOnClickOutside";
import type { TagResponse, MoodResponse } from "@/lib/api/entries";

interface EditorPropertiesProps {
  entryId: string;
}

export const EditorProperties: React.FC<EditorPropertiesProps> = ({ entryId }) => {
  const { entries, updateEntry, addTag, removeTag, fetchMoods } = useJournalStore();
  const { tags, fetchTags, createTag } = useTagStore();
  const { collections, fetchCollections, addEntryToCollection } = useCollectionStore();

  const [showTagInput, setShowTagInput] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#888888");

  const [showCollectionMenu, setShowCollectionMenu] = useState(false);
  const [showMoodMenu, setShowMoodMenu] = useState(false);

  const collectionMenuRef = useRef<HTMLDivElement>(null);
  useOnClickOutside(collectionMenuRef, () => setShowCollectionMenu(false));

  const tagMenuRef = useRef<HTMLDivElement>(null);
  useOnClickOutside(tagMenuRef, () => setShowTagInput(false));

  const moodMenuRef = useRef<HTMLDivElement>(null);
  useOnClickOutside(moodMenuRef, () => setShowMoodMenu(false));

  const [selectingMoodId, setSelectingMoodId] = useState<string | null>(null);
  const [moodIntensity, setMoodIntensity] = useState<number>(5);

  const { summaries, getSummaryForEntry } = useAIStore();
  const [isSummaryExpanded, setIsSummaryExpanded] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const summary = summaries[`entry-${entryId}`];

  const entry = entries[entryId];

  useEffect(() => {
    fetchTags();
    fetchCollections();
    fetchMoods();
  }, [fetchTags, fetchCollections, fetchMoods]);

  if (!entry) return null;

  const toggleFavorite = () => {
    updateEntry(entryId, { is_favorite: !entry.is_favorite });
  };

  const handleAddTag = async (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && newTagName.trim()) {
      const name = newTagName.trim();
      let tag = tags.find((t) => t.name.toLowerCase() === name.toLowerCase());
      if (!tag) {
        tag = await createTag({ name, color: newTagColor });
      }
      if (!entry.tags?.find((t) => t.id === tag!.id)) {
        await addTag(entryId, tag.id);
      }
      setNewTagName("");
      setShowTagInput(false);
    }
  };

  const handleRemoveTag = (tagId: string) => {
    removeTag(entryId, tagId);
  };

  const handleToggleCollection = async (collectionId: string) => {
    await addEntryToCollection(collectionId, entryId);
    setShowCollectionMenu(false);
  };

  return (
    <div className="mb-6 flex min-w-0 flex-col gap-3 border-b border-[var(--border-soft)] py-4 text-sm text-[var(--text-muted)]">
      <div className="flex flex-wrap items-center gap-4">
        <button
          onClick={toggleFavorite}
          className={`flex items-center gap-1.5 transition-colors ${entry.is_favorite ? "text-yellow-500 hover:text-yellow-600" : "hover:text-[var(--ink-color)]"}`}
        >
          <Star size={16} fill={entry.is_favorite ? "currentColor" : "none"} />
          <span>Favorite</span>
        </button>

        <div className="relative" ref={collectionMenuRef}>
          <button
            onClick={() => setShowCollectionMenu(!showCollectionMenu)}
            className="flex items-center gap-1.5 transition-colors hover:text-[var(--ink-color)]"
          >
            <Folder size={16} />
            <span>Add to Collection</span>
          </button>

          {showCollectionMenu && (
            <div className="absolute top-full left-0 z-50 mt-2 flex w-48 flex-col gap-1 rounded-md border border-[var(--border-soft)] bg-[var(--bg-color)] p-1 shadow-lg">
              {Object.values(collections).length === 0 ? (
                <div className="px-2 py-1.5 text-xs opacity-50">No collections found</div>
              ) : (
                Object.values(collections).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => handleToggleCollection(c.id)}
                    className="rounded-sm px-2 py-1.5 text-left text-[var(--ink-color)] hover:bg-[var(--border-soft)]"
                  >
                    {c.name}
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button
          onClick={async () => {
            if (isSummaryExpanded) {
              setIsSummaryExpanded(false);
              return;
            }
            setIsSummaryExpanded(true);
            if (!summary) {
              setIsSummarizing(true);
              try {
                await getSummaryForEntry(entryId);
              } catch (e) {
                console.error(e);
              }
              setIsSummarizing(false);
            }
          }}
          className={`flex items-center gap-1.5 transition-colors ${
            isSummaryExpanded || summary
              ? "text-[var(--accent-color)] hover:opacity-80"
              : "hover:text-[var(--ink-color)]"
          }`}
        >
          {isSummarizing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          <span>{summary ? "View Summary" : "Generate Summary"}</span>
        </button>
      </div>

      {isSummaryExpanded && (
        <div className="mt-2 flex w-full min-w-0 flex-col gap-3 overflow-hidden rounded-lg border border-[var(--border-soft)] bg-[var(--card-bg)] p-4 text-sm text-[var(--ink-color)] shadow-md">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 font-serif text-base font-bold text-[var(--accent-color)]">
              <Sparkles size={16} /> AI Summary
            </h3>
            <button
              onClick={() => setIsSummaryExpanded(false)}
              className="opacity-50 hover:opacity-100"
            >
              <X size={16} />
            </button>
          </div>

          {isSummarizing ? (
            <div className="flex items-center gap-2 opacity-60">
              <Loader2 size={14} className="animate-spin" />
              <span>Analyzing entry...</span>
            </div>
          ) : summary ? (
            <div className="min-w-0">
              <p className="leading-relaxed break-words opacity-90">{summary.content}</p>
            </div>
          ) : (
            <div className="opacity-50">
              Could not generate summary. Ensure the entry has enough content.
            </div>
          )}
        </div>
      )}

      <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2">
        <Tag size={16} className="shrink-0 opacity-50" />
        {entry.tags?.map((tag: TagResponse) => (
          <span
            key={tag.id}
            className="flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: `${tag.color}15`,
              color: tag.color,
              borderColor: `${tag.color}40`,
            }}
          >
            <span className="truncate">{tag.name}</span>
            <button
              onClick={() => handleRemoveTag(tag.id)}
              className="shrink-0 opacity-50 transition-opacity hover:opacity-100"
            >
              <X size={12} />
            </button>
          </span>
        ))}

        {showTagInput ? (
          <div className="relative" ref={tagMenuRef}>
            <div className="flex max-w-full items-center gap-2 rounded-full border border-[var(--border-soft)] bg-[var(--card-bg)] px-2 py-1 shadow-sm">
              <input
                type="text"
                autoFocus
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setShowTagInput(false);
                    setNewTagName("");
                  } else {
                    handleAddTag(e);
                  }
                }}
                placeholder="Type and enter..."
                className="w-24 min-w-[80px] border-none bg-transparent px-1 text-xs text-[var(--ink-color)] outline-none"
              />
              <div className="flex shrink-0 items-center gap-1">
                <input
                  type="color"
                  value={newTagColor}
                  onChange={(e) => setNewTagColor(e.target.value)}
                  className="h-6 w-6 cursor-pointer rounded-full border-none bg-transparent p-0 outline-none [&::-moz-color-swatch]:rounded-full [&::-moz-color-swatch]:border-none [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-none [&::-webkit-color-swatch-wrapper]:p-0"
                  title="Choose tag color"
                />
                <button
                  onClick={() => setShowTagInput(false)}
                  className="p-1 opacity-50 hover:opacity-100"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Tag Autocomplete Dropdown */}
            {newTagName.trim() &&
              tags.filter(
                (t) =>
                  t.name.toLowerCase().includes(newTagName.toLowerCase()) &&
                  !entry.tags?.find((et) => et.id === t.id),
              ).length > 0 && (
                <div className="absolute top-full left-0 z-50 mt-2 flex max-h-48 w-48 max-w-[90vw] flex-col gap-1 overflow-y-auto rounded-md border border-[var(--border-soft)] bg-[var(--card-bg)] p-1 shadow-lg backdrop-blur-md">
                  <div className="mb-1 border-b border-[var(--border-soft)] px-2 py-1 text-xs opacity-50">
                    Use existing tag
                  </div>
                  {tags
                    .filter(
                      (t) =>
                        t.name.toLowerCase().includes(newTagName.toLowerCase()) &&
                        !entry.tags?.find((et) => et.id === t.id),
                    )
                    .map((t) => (
                      <button
                        key={t.id}
                        onClick={async () => {
                          await addTag(entryId, t.id);
                          setNewTagName("");
                          setShowTagInput(false);
                        }}
                        className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-left text-xs font-medium transition-colors hover:bg-[var(--border-soft)]"
                      >
                        <div
                          className="h-2 w-2 shrink-0 rounded-full"
                          style={{ backgroundColor: t.color }}
                        />
                        <span className="truncate text-[var(--ink-color)]">{t.name}</span>
                      </button>
                    ))}
                </div>
              )}
          </div>
        ) : (
          <button
            onClick={() => setShowTagInput(true)}
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--border-soft)]"
          >
            <Plus size={14} />
          </button>
        )}
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <Star size={16} className="shrink-0 opacity-50" />
        {entry.moods?.map((mood: MoodResponse) => (
          <span
            key={mood.id}
            className="flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium"
            style={{
              backgroundColor: `${mood.color}15`,
              color: mood.color,
              borderColor: `${mood.color}40`,
            }}
          >
            <span className="truncate">
              {mood.name} {mood.intensity}/10
            </span>
            <button
              onClick={() => useJournalStore.getState().removeMood(entryId, mood.id)}
              className="shrink-0 opacity-50 transition-opacity hover:opacity-100"
            >
              <X size={12} />
            </button>
          </span>
        ))}

        <div className="relative" ref={moodMenuRef}>
          <button
            onClick={() => setShowMoodMenu(!showMoodMenu)}
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--border-soft)]"
          >
            <Plus size={14} />
          </button>

          {showMoodMenu && (
            <div className="absolute top-full left-0 z-50 mt-2 flex w-64 max-w-[90vw] flex-col gap-1 rounded-md border border-[var(--border-soft)] bg-[var(--card-bg)] p-2 shadow-lg backdrop-blur-md">
              {selectingMoodId ? (
                <div className="flex flex-col gap-2 p-1">
                  <div className="flex items-center justify-between">
                    <span
                      className="truncate text-xs font-medium"
                      style={{
                        color: useJournalStore
                          .getState()
                          .availableMoods.find((m) => m.id === selectingMoodId)?.color,
                      }}
                    >
                      Rate{" "}
                      {
                        useJournalStore
                          .getState()
                          .availableMoods.find((m) => m.id === selectingMoodId)?.name
                      }
                    </span>
                    <button
                      onClick={() => setSelectingMoodId(null)}
                      className="shrink-0 opacity-50 hover:opacity-100"
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="range"
                      min="1"
                      max="10"
                      value={moodIntensity}
                      onChange={(e) => setMoodIntensity(parseInt(e.target.value))}
                      className="min-w-0 flex-1"
                    />
                    <span className="w-4 shrink-0 text-center text-xs font-bold">
                      {moodIntensity}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      useJournalStore.getState().addMood(entryId, selectingMoodId, moodIntensity);
                      setSelectingMoodId(null);
                      setMoodIntensity(5);
                      setShowMoodMenu(false);
                    }}
                    className="mt-1 w-full rounded-md bg-[var(--ink-color)] py-1 text-xs font-bold text-[var(--bg-color)] transition-transform hover:scale-[1.02] active:scale-95"
                  >
                    Save
                  </button>
                </div>
              ) : useJournalStore.getState().availableMoods.length === 0 ? (
                <div className="px-2 py-1.5 text-xs opacity-50">No moods found</div>
              ) : (
                <div className="grid grid-cols-2 gap-1">
                  {useJournalStore.getState().availableMoods.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        setSelectingMoodId(m.id);
                        setMoodIntensity(5);
                      }}
                      className="flex items-center justify-center rounded-sm border border-transparent px-2 py-1.5 text-left text-xs font-medium transition-colors hover:border-[var(--border-soft)] hover:bg-[var(--border-soft)]"
                      style={{ color: m.color, backgroundColor: `${m.color}15` }}
                    >
                      <span className="truncate">{m.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
