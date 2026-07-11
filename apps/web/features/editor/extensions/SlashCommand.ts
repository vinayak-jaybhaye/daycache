import { Extension } from "@tiptap/core";
import Suggestion, { type SuggestionProps, type SuggestionKeyDownProps } from "@tiptap/suggestion";
import { ReactRenderer } from "@tiptap/react";
import tippy, { Instance } from "tippy.js";
import { SlashCommandList, SlashCommandListRef } from "../components/SlashCommandList";
import { slashCommands, SlashCommand, SlashCommandContext } from "../commands/registry";
import type { Editor, Range } from "@tiptap/core";

export interface SlashCommandOptions {
  context: Omit<SlashCommandContext, "editor">;
  suggestion: Omit<Parameters<typeof Suggestion>[0], "editor" | "command">;
}

export const SlashCommandExtension = Extension.create<SlashCommandOptions>({
  name: "slashCommand",

  addOptions() {
    return {
      context: {} as Omit<SlashCommandContext, "editor">,
      suggestion: {
        char: "/",
        command: () => {
          // This will be overridden in addProseMirrorPlugins to access this.options
        },
      },
    };
  },

  addProseMirrorPlugins() {
    return [
      Suggestion({
        editor: this.editor,
        ...this.options.suggestion,
        command: ({
          editor,
          range,
          props: item,
        }: {
          editor: Editor;
          range: Range;
          props: unknown;
        }) => {
          const cmd = item as SlashCommand;
          cmd.run({
            editor,
            ...this.options.context,
          } as SlashCommandContext);

          editor.chain().focus().deleteRange(range).run();
        },
      }),
    ];
  },
});

/**
 * Creates the standard suggestion configuration for the SlashCommand extension.
 */
export function getSlashSuggestionConfig() {
  return {
    items: ({ query, editor }: { query: string; editor: Editor }) => {
      const normalizedQuery = query.toLowerCase().trim();

      // Filter by visibility first
      const visibleCommands = slashCommands.filter((cmd) => cmd.isVisible(editor));

      if (!normalizedQuery) {
        // Sort by priority
        return visibleCommands.sort((a, b) => b.priority - a.priority);
      }

      return visibleCommands
        .filter((cmd) => {
          const matchTitle = cmd.title.toLowerCase().includes(normalizedQuery);
          const matchDesc = cmd.description?.toLowerCase().includes(normalizedQuery);
          const matchKeywords = cmd.keywords.some((k) => k.toLowerCase().includes(normalizedQuery));
          const matchAliases = cmd.aliases.some((a) => a.toLowerCase().includes(normalizedQuery));

          return matchTitle || matchDesc || matchKeywords || matchAliases;
        })
        .sort((a, b) => b.priority - a.priority);
    },

    render: () => {
      let component: ReactRenderer<SlashCommandListRef>;
      let popup: Instance[];

      return {
        onStart: (props: SuggestionProps) => {
          component = new ReactRenderer(SlashCommandList, {
            props,
            editor: props.editor,
          });

          if (!props.clientRect) {
            return;
          }

          const clientRect = props.clientRect;

          popup = [
            tippy(document.body, {
              getReferenceClientRect: () => clientRect?.() ?? new DOMRect(),
              appendTo: () => document.body,
              content: component.element,
              showOnCreate: true,
              interactive: true,
              trigger: "manual",
              placement: "bottom-start",
              theme: "light",
              animation: "shift-away",
            }),
          ];
        },

        onUpdate(props: SuggestionProps) {
          if (!component) return;
          component.updateProps(props);

          if (!props.clientRect || !popup?.[0]) {
            return;
          }

          popup[0].setProps({
            getReferenceClientRect: () => props.clientRect?.() ?? new DOMRect(),
          });
        },

        onKeyDown(props: SuggestionKeyDownProps) {
          if (props.event.key === "Escape" && popup?.[0]) {
            popup[0].hide();
            return true;
          }

          return component?.ref?.onKeyDown(props) || false;
        },

        onExit() {
          popup?.[0]?.destroy();
          component?.destroy();
        },
      };
    },
  };
}
