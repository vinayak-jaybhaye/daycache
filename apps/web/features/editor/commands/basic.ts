import React from "react";
import { Type, Heading1, Heading2, Heading3 } from "lucide-react";
import type { SlashCommand } from "./registry";

export const basicCommands: SlashCommand[] = [
  {
    id: "paragraph",
    title: "Text",
    description: "Start writing with plain text.",
    icon: React.createElement(Type, { size: 18 }),
    group: "basic",
    aliases: ["p", "paragraph", "text"],
    keywords: ["text", "paragraph", "type", "write", "normal"],
    priority: 100,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().setParagraph().run();
    },
  },
  {
    id: "heading-1",
    title: "Heading 1",
    description: "Big section heading.",
    icon: React.createElement(Heading1, { size: 18 }),
    group: "basic",
    aliases: ["h1", "header", "title", "heading 1"],
    keywords: ["h1", "heading", "title", "big"],
    shortcut: "⌘⌥1",
    priority: 90,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().setHeading({ level: 1 }).run();
    },
  },
  {
    id: "heading-2",
    title: "Heading 2",
    description: "Medium section heading.",
    icon: React.createElement(Heading2, { size: 18 }),
    group: "basic",
    aliases: ["h2", "header", "subtitle", "heading 2"],
    keywords: ["h2", "heading", "subtitle", "medium"],
    shortcut: "⌘⌥2",
    priority: 85,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().setHeading({ level: 2 }).run();
    },
  },
  {
    id: "heading-3",
    title: "Heading 3",
    description: "Small section heading.",
    icon: React.createElement(Heading3, { size: 18 }),
    group: "basic",
    aliases: ["h3", "header", "heading 3"],
    keywords: ["h3", "heading", "small"],
    shortcut: "⌘⌥3",
    priority: 80,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().setHeading({ level: 3 }).run();
    },
  },
];
