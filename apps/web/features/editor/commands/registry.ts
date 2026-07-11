import { Editor } from "@tiptap/core";
import { ReactNode } from "react";

export type SlashGroup = "basic" | "lists" | "media" | "blocks" | "ai";

export interface SlashCommandContext {
  editor: Editor;
  triggerImageUpload: () => void;
}

export interface SlashCommand {
  id: string;
  title: string;
  description?: string;
  icon: ReactNode;
  group: SlashGroup;
  aliases: string[];
  keywords: string[];
  shortcut?: string;
  priority: number;
  isVisible: (editor: Editor) => boolean;
  isEnabled: (editor: Editor) => boolean;
  run: (ctx: SlashCommandContext) => void | Promise<void>;
}

import { basicCommands } from "./basic";
import { listCommands } from "./lists";
import { blockCommands } from "./blocks";
import { mediaCommands } from "./media";

export const slashCommands: SlashCommand[] = [
  ...basicCommands,
  ...listCommands,
  ...blockCommands,
  ...mediaCommands,
];
