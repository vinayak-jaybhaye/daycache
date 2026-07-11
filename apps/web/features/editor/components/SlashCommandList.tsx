import React, { forwardRef, useEffect, useImperativeHandle, useState, useRef } from "react";
import { type SlashCommand, type SlashGroup } from "../commands/registry";
import { Editor } from "@tiptap/core";

export interface SlashCommandListRef {
  onKeyDown: (props: { event: KeyboardEvent }) => boolean;
}

interface SlashCommandListProps {
  editor: Editor;
  items: SlashCommand[];
  command: (command: SlashCommand) => void;
  clientRect?: () => DOMRect;
}

const GROUP_LABELS: Record<SlashGroup, string> = {
  basic: "Basic",
  lists: "Lists",
  blocks: "Blocks",
  media: "Media",
  ai: "AI",
};

export const SlashCommandList = forwardRef<SlashCommandListRef, SlashCommandListProps>(
  ({ editor, items, command }, ref) => {
    const [selectedIndex, setSelectedIndex] = useState(0);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Group items for rendering
    const groups = items.reduce(
      (acc, item) => {
        if (!acc[item.group]) {
          acc[item.group] = [];
        }
        acc[item.group].push(item);
        return acc;
      },
      {} as Record<string, SlashCommand[]>,
    );

    const groupKeys = Object.keys(groups) as SlashGroup[];

    useEffect(() => {
      setSelectedIndex(0);
    }, [items]);

    useImperativeHandle(ref, () => ({
      onKeyDown: ({ event }) => {
        if (event.key === "ArrowUp") {
          setSelectedIndex((prevIndex) => (prevIndex + items.length - 1) % items.length);
          return true;
        }
        if (event.key === "ArrowDown") {
          setSelectedIndex((prevIndex) => (prevIndex + 1) % items.length);
          return true;
        }
        if (event.key === "Enter") {
          const item = items[selectedIndex];
          if (item && item.isEnabled(editor)) {
            command(item);
          }
          return true;
        }
        return false;
      },
    }));

    // Auto-scroll selected item into view
    useEffect(() => {
      const container = scrollContainerRef.current;
      if (!container) return;
      const selectedEl = container.querySelector(".slash-command-selected") as HTMLElement;
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
      }
    }, [selectedIndex]);

    if (items.length === 0) {
      return null;
    }

    let globalIndex = 0;

    return (
      <div
        ref={scrollContainerRef}
        className="z-50 flex max-h-[300px] w-72 flex-col gap-1 overflow-y-auto rounded-xl border border-[var(--border-soft)] bg-[var(--card-bg)] p-2 shadow-lg backdrop-blur-md"
        style={{ scrollbarWidth: "thin" }}
      >
        {groupKeys.map((group) => (
          <div key={group} className="flex flex-col">
            <div className="px-2 py-1.5 text-xs font-semibold tracking-wider text-[var(--text-muted)] uppercase">
              {GROUP_LABELS[group]}
            </div>
            {groups[group].map((item) => {
              const currentIndex = globalIndex++;
              const isSelected = currentIndex === selectedIndex;
              const enabled = item.isEnabled(editor);

              return (
                <button
                  key={item.id}
                  className={`flex items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors ${
                    isSelected
                      ? "slash-command-selected bg-[var(--border-soft)]"
                      : "hover:bg-[var(--border-soft)]/50"
                  } ${!enabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                  onClick={() => enabled && command(item)}
                  onMouseEnter={() => setSelectedIndex(currentIndex)}
                >
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--bg-color)] text-[var(--ink-color)] shadow-sm">
                    {item.icon}
                  </div>
                  <div className="flex flex-1 flex-col justify-center overflow-hidden">
                    <span className="truncate text-sm font-medium text-[var(--ink-color)]">
                      {item.title}
                    </span>
                    {item.description && (
                      <span className="truncate text-xs text-[var(--text-muted)]">
                        {item.description}
                      </span>
                    )}
                  </div>
                  {item.shortcut && (
                    <span className="rounded bg-[var(--bg-color)] px-1.5 py-0.5 font-mono text-xs text-[var(--text-muted)]">
                      {item.shortcut}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    );
  },
);

SlashCommandList.displayName = "SlashCommandList";
