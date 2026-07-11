"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  Calendar,
  Feather,
  MessageCircle,
  Search,
  Settings,
  Notebook,
  Star,
  Plus,
  Trash2,
  Edit2,
  ChevronRight,
  ChevronDown,
  Menu,
  X,
} from "lucide-react";
import { useUIStore } from "@/store/useUIStore";
import { useJournalStore } from "@/store/useJournalStore";
import { useCollectionStore } from "@/store/useCollectionStore";
import { useTagStore } from "@/store/useTagStore";

export const Sidebar = () => {
  const pathname = usePathname();
  const { isSidebarOpen, setSidebarOpen } = useUIStore();
  const { currentFilter, setFilter } = useJournalStore();
  const { collections, fetchCollections, createCollection, deleteCollection, updateCollection } =
    useCollectionStore();
  const { tags, fetchTags, createTag, deleteTag } = useTagStore();

  const [showCollections, setShowCollections] = useState(true);
  const [showTags, setShowTags] = useState(true);

  const [isCreatingCollection, setIsCreatingCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");

  const [isCreatingTag, setIsCreatingTag] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#8B9BB4");

  const [editingCollectionId, setEditingCollectionId] = useState<string | null>(null);
  const [editCollectionName, setEditCollectionName] = useState("");

  useEffect(() => {
    fetchCollections();
    fetchTags();
  }, [fetchCollections, fetchTags]);

  const navItems = [
    { id: "home", href: "/", icon: Home, label: "Scrapbook" },
    { id: "calendar", href: "/timeline", icon: Calendar, label: "Timeline" },
    { id: "reflect", href: "/reflect", icon: Feather, label: "Reflect" },
    { id: "recall", href: "/recall", icon: MessageCircle, label: "Recall" },
    { id: "search", href: "/search", icon: Search, label: "Search" },
    { id: "settings", href: "/settings", icon: Settings, label: "Settings" },
  ];

  const handleCreateCollection = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && newCollectionName.trim()) {
      await createCollection(newCollectionName.trim());
      setNewCollectionName("");
      setIsCreatingCollection(false);
    } else if (e.key === "Escape") {
      setIsCreatingCollection(false);
    }
  };

  const handleCreateTag = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && newTagName.trim()) {
      await createTag({ name: newTagName.trim(), color: newTagColor });
      setNewTagName("");
      setIsCreatingTag(false);
    } else if (e.key === "Escape") {
      setIsCreatingTag(false);
    }
  };

  const handleUpdateCollection = async (id: string) => {
    if (editCollectionName.trim()) {
      await updateCollection(id, { name: editCollectionName.trim() });
    }
    setEditingCollectionId(null);
  };

  if (!isSidebarOpen) {
    return (
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed top-4 left-4 z-[60] cursor-pointer rounded-full border border-[var(--border-soft)] bg-[var(--card-bg)] p-2 text-[var(--text-muted)] shadow-sm transition-colors hover:text-[var(--ink-color)]"
      >
        <Menu size={20} />
      </button>
    );
  }

  return (
    <>
      <div
        className="fixed inset-0 z-[55] bg-black/20 backdrop-blur-sm transition-opacity md:hidden"
        onClick={() => setSidebarOpen(false)}
      />
      <motion.div
        initial={{ x: -300 }}
        animate={{ x: 0 }}
        exit={{ x: -300 }}
        className="fixed top-0 left-0 z-[60] flex h-screen w-64 flex-col border-r border-[var(--border-soft)] bg-[var(--bg-color)] shadow-xl"
      >
        <div className="mt-2 mb-4 flex shrink-0 items-center justify-between p-4">
          <h1 className="px-2 font-serif text-2xl font-bold tracking-tight text-[var(--ink-color)]">
            DayCache
          </h1>
          <button
            onClick={() => setSidebarOpen(false)}
            className="cursor-pointer rounded-full p-1.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--border-soft)] hover:text-[var(--ink-color)]"
          >
            <Menu size={18} />
          </button>
        </div>

        <div className="hide-scrollbar flex-1 overflow-x-hidden overflow-y-auto pb-8">
          <div className="space-y-0.5 px-3 py-2">
            {navItems.map(({ id, href, icon: Icon, label }) => {
              const isActive = pathname === href && currentFilter.type === "all";
              return (
                <Link
                  key={id}
                  href={href}
                  onClick={() => {
                    setFilter({ type: "all" });
                    if (window.innerWidth < 768) setSidebarOpen(false);
                  }}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-[var(--ink-color)] text-[var(--bg-color)] shadow-md"
                      : "text-[var(--text-muted)] hover:bg-[var(--border-soft)]/50 hover:text-[var(--ink-color)]"
                  }`}
                >
                  <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
                  {label}
                </Link>
              );
            })}
          </div>

          <div className="px-3">
            <Link
              href="/favorites"
              onClick={() => {
                if (window.innerWidth < 768) setSidebarOpen(false);
              }}
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                pathname === "/favorites"
                  ? "bg-[var(--card-bg)] font-medium text-[var(--ink-color)] shadow-sm"
                  : "text-[var(--text-muted)] hover:bg-[var(--border-soft)]/50 hover:text-[var(--ink-color)]"
              }`}
            >
              <Star size={16} />
              Favorites
            </Link>
          </div>

          <div className="group mt-6 flex items-center justify-between px-2">
            <button
              onClick={() => setShowCollections(!showCollections)}
              className="flex items-center gap-2 px-2 text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase hover:text-[var(--ink-color)]"
            >
              {showCollections ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <span>Collections</span>
            </button>
            <button
              onClick={() => setIsCreatingCollection(true)}
              className="rounded p-1 text-[var(--text-muted)] opacity-100 transition-all lg:opacity-0 lg:group-hover:opacity-100 lg:hover:bg-[var(--border-soft)]/50 lg:hover:text-[var(--ink-color)]"
            >
              <Plus size={14} />
            </button>
          </div>

          <AnimatePresence>
            {showCollections && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-1 space-y-0.5 overflow-hidden px-3"
              >
                {isCreatingCollection && (
                  <div className="flex items-center gap-2 rounded-lg bg-[var(--card-bg)] px-3 py-1.5 shadow-sm">
                    <Notebook size={16} className="shrink-0 text-[var(--text-muted)]" />
                    <input
                      type="text"
                      autoFocus
                      value={newCollectionName}
                      onChange={(e) => setNewCollectionName(e.target.value)}
                      onKeyDown={handleCreateCollection}
                      onBlur={() => setIsCreatingCollection(false)}
                      placeholder="Collection name..."
                      className="w-full border-none bg-transparent text-sm text-[var(--ink-color)] outline-none"
                    />
                  </div>
                )}

                {Object.values(collections).map((c) => {
                  const isEditing = editingCollectionId === c.id;

                  return (
                    <div
                      key={c.id}
                      className={`group flex items-center justify-between rounded-lg px-3 py-1.5 text-sm transition-colors ${
                        pathname === `/collection/${c.id}`
                          ? "bg-[var(--card-bg)] font-medium text-[var(--ink-color)] shadow-sm"
                          : "text-[var(--text-muted)] hover:bg-[var(--border-soft)]/50 hover:text-[var(--ink-color)]"
                      }`}
                    >
                      {isEditing ? (
                        <div className="flex w-full items-center gap-2">
                          <Notebook size={16} className="shrink-0" />
                          <input
                            type="text"
                            autoFocus
                            value={editCollectionName}
                            onChange={(e) => setEditCollectionName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleUpdateCollection(c.id);
                              if (e.key === "Escape") setEditingCollectionId(null);
                            }}
                            onBlur={() => handleUpdateCollection(c.id)}
                            className="w-full border-none bg-transparent text-sm text-[var(--ink-color)] outline-none"
                          />
                        </div>
                      ) : (
                        <>
                          <Link
                            href={`/collection/${c.id}`}
                            onClick={() => {
                              if (window.innerWidth < 768) setSidebarOpen(false);
                            }}
                            className="flex flex-1 items-center gap-3 truncate text-left"
                          >
                            <Notebook size={16} className="shrink-0" />
                            <span className="truncate">{c.name}</span>
                          </Link>
                          <div className="flex items-center gap-1 opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100">
                            <button
                              onClick={() => {
                                setEditingCollectionId(c.id);
                                setEditCollectionName(c.name);
                              }}
                              className="rounded p-1 text-[var(--text-muted)] lg:hover:bg-[var(--border-soft)] lg:hover:text-[var(--ink-color)]"
                            >
                              <Edit2 size={12} />
                            </button>
                            <button
                              onClick={() => deleteCollection(c.id)}
                              className="rounded p-1 text-[var(--text-muted)] lg:hover:bg-[var(--border-soft)] lg:hover:text-red-500"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="group mt-6 flex items-center justify-between px-2">
            <button
              onClick={() => setShowTags(!showTags)}
              className="flex items-center gap-2 px-2 text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase hover:text-[var(--ink-color)]"
            >
              {showTags ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <span>Tags</span>
            </button>
            <button
              onClick={() => setIsCreatingTag(true)}
              className="rounded p-1 text-[var(--text-muted)] opacity-100 transition-all lg:opacity-0 lg:group-hover:opacity-100 lg:hover:bg-[var(--border-soft)]/50 lg:hover:text-[var(--ink-color)]"
            >
              <Plus size={14} />
            </button>
          </div>

          <AnimatePresence>
            {showTags && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-1 space-y-0.5 overflow-hidden px-3 pb-8"
              >
                {isCreatingTag && (
                  <div className="flex items-center gap-2 rounded-lg bg-[var(--card-bg)] px-3 py-1.5 shadow-sm">
                    <input
                      type="color"
                      value={newTagColor}
                      onChange={(e) => setNewTagColor(e.target.value)}
                      className="h-4 w-4 shrink-0 cursor-pointer rounded-full border-none bg-transparent p-0 outline-none [&::-moz-color-swatch]:rounded-full [&::-moz-color-swatch]:border-none [&::-webkit-color-swatch]:rounded-full [&::-webkit-color-swatch]:border-none [&::-webkit-color-swatch-wrapper]:p-0"
                      title="Choose tag color"
                    />
                    <input
                      type="text"
                      autoFocus
                      value={newTagName}
                      onChange={(e) => setNewTagName(e.target.value)}
                      onKeyDown={handleCreateTag}
                      placeholder="Tag name..."
                      className="w-full border-none bg-transparent text-sm text-[var(--ink-color)] outline-none"
                    />
                    <button
                      onClick={() => setIsCreatingTag(false)}
                      className="shrink-0 p-1 opacity-50 hover:opacity-100"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}

                {tags.map((tag) => {
                  return (
                    <div
                      key={tag.id}
                      className={`group flex items-center justify-between rounded-lg px-3 py-1.5 text-sm transition-colors ${
                        pathname === `/tag/${tag.id}`
                          ? "bg-[var(--card-bg)] font-medium text-[var(--ink-color)] shadow-sm"
                          : "text-[var(--text-muted)] lg:hover:bg-[var(--border-soft)]/50 lg:hover:text-[var(--ink-color)]"
                      }`}
                    >
                      <Link
                        href={`/tag/${tag.id}`}
                        onClick={() => {
                          if (window.innerWidth < 768) setSidebarOpen(false);
                        }}
                        className="flex flex-1 items-center gap-2 truncate text-left"
                      >
                        <span
                          className="truncate rounded-md px-2 py-0.5 text-xs font-medium"
                          style={{ backgroundColor: `${tag.color}20`, color: tag.color }}
                        >
                          #{tag.name}
                        </span>
                      </Link>
                      <div className="flex items-center gap-1 opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100">
                        <button
                          onClick={() => deleteTag(tag.id)}
                          className="rounded p-1 text-[var(--text-muted)] lg:hover:bg-[var(--border-soft)] lg:hover:text-red-500"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </>
  );
};
