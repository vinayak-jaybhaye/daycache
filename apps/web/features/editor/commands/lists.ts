import React from "react";
import { List, ListOrdered, CheckSquare } from "lucide-react";
import type { SlashCommand } from "./registry";

export const listCommands: SlashCommand[] = [
  {
    id: "bullet-list",
    title: "Bullet List",
    description: "Create a simple bulleted list.",
    icon: React.createElement(List, { size: 18 }),
    group: "lists",
    aliases: ["ul", "unordered", "bullet", "list"],
    keywords: ["bullet", "list", "unordered", "point"],
    shortcut: "⌘⇧8",
    priority: 70,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().toggleBulletList().run();
    },
  },
  {
    id: "ordered-list",
    title: "Numbered List",
    description: "Create a list with numbering.",
    icon: React.createElement(ListOrdered, { size: 18 }),
    group: "lists",
    aliases: ["ol", "ordered", "numbered", "number"],
    keywords: ["number", "list", "ordered", "step"],
    shortcut: "⌘⇧7",
    priority: 65,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().toggleOrderedList().run();
    },
  },
  {
    id: "task-list",
    title: "To-do List",
    description: "Track tasks with a to-do list.",
    icon: React.createElement(CheckSquare, { size: 18 }),
    group: "lists",
    aliases: ["todo", "task", "checklist", "check", "[]"],
    keywords: ["todo", "task", "checklist", "box", "done"],
    shortcut: "⌘⇧9",
    priority: 75,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().toggleTaskList().run();
    },
  },
];
