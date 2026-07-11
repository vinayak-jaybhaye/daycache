import React from "react";
import { Image as ImageIcon } from "lucide-react";
import type { SlashCommand } from "./registry";

export const mediaCommands: SlashCommand[] = [
  {
    id: "upload-image",
    title: "Upload Image",
    description: "Upload or embed with a link.",
    icon: React.createElement(ImageIcon, { size: 18 }),
    group: "media",
    aliases: ["image", "img", "picture", "photo", "upload"],
    keywords: ["image", "upload", "picture", "photo", "media"],
    priority: 85,
    isVisible: () => true,
    isEnabled: () => true,
    run: ({ triggerImageUpload }) => {
      triggerImageUpload();
    },
  },
];
