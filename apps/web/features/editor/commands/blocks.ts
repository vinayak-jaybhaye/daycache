import React from "react";
import { Quote, Minus, CodeSquare } from "lucide-react";
import type { SlashCommand } from "./registry";

export const blockCommands: SlashCommand[] = [
  {
    id: "blockquote",
    title: "Quote",
    description: "Capture a quote.",
    icon: React.createElement(Quote, { size: 18 }),
    group: "blocks",
    aliases: ["quote", "blockquote", ">"],
    keywords: ["quote", "blockquote", "saying", "cite"],
    shortcut: "⌘⇧B",
    priority: 60,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().toggleBlockquote().run();
    },
  },
  {
    id: "divider",
    title: "Divider",
    description: "Visually divide blocks.",
    icon: React.createElement(Minus, { size: 18 }),
    group: "blocks",
    aliases: ["hr", "divider", "line", "horizontal rule", "---"],
    keywords: ["divider", "line", "rule", "break", "separator"],
    priority: 55,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().setHorizontalRule().run();
    },
  },
  {
    id: "code-block",
    title: "Code Block",
    description: "Capture a code snippet.",
    icon: React.createElement(CodeSquare, { size: 18 }),
    group: "blocks",
    aliases: ["code", "snippet", "```", "pre"],
    keywords: ["code", "snippet", "block", "programming", "script"],
    shortcut: "⌘⌥C",
    priority: 50,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ editor }) => {
      editor.chain().focus().toggleCodeBlock().run();
    },
  },
];
