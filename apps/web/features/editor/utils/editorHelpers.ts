/**
 * Utility functions for common editor operations.
 * These are pure functions with no side effects.
 */

import type { Editor } from "@tiptap/react";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

/**
 * Check if the editor is in a specific block type.
 * @param editor The TipTap editor instance
 * @param blockType Block type name (e.g., "paragraph", "heading")
 * @returns true if cursor is in that block type
 */
export function isInBlockType(editor: Editor, blockType: string): boolean {
  return editor.isActive(blockType);
}

/**
 * Get the current block's text content.
 * Useful for markdown shortcuts detection.
 */
export function getCurrentBlockText(editor: Editor): string {
  const { $anchor } = editor.state.selection;
  const node = $anchor.parent;
  return node.textContent;
}

/**
 * Check if selection is at the start of a line.
 * Used for markdown shortcuts like "# " → heading.
 */
export function isAtStartOfLine(editor: Editor): boolean {
  const { $from } = editor.state.selection;
  return $from.parentOffset === 0;
}

/**
 * Check if selection is empty (collapsed cursor).
 */
export function isSelectionEmpty(editor: Editor): boolean {
  const { from, to } = editor.state.selection;
  return from === to;
}

/**
 * Get selected text content.
 */
export function getSelectedText(editor: Editor): string {
  return editor.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, " ");
}

/**
 * Extract all mediaImage nodes from the document.
 * Returns array of { pos, node, attrs }.
 */
export function extractMediaNodes(editor: Editor): Array<{
  pos: number;
  node: ProseMirrorNode;
  attrs: Record<string, unknown>;
}> {
  const nodes: Array<{ pos: number; node: ProseMirrorNode; attrs: Record<string, unknown> }> = [];

  editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "mediaImage") {
      nodes.push({ pos, node, attrs: node.attrs });
    }
  });

  return nodes;
}

/**
 * Extract all media IDs from the document.
 * Used for backend reconciliation on save.
 */
export function extractMediaIds(editor: Editor): string[] {
  const ids: string[] = [];

  editor.state.doc.descendants((node) => {
    if (node.type.name === "mediaImage" && node.attrs?.mediaId) {
      ids.push(node.attrs.mediaId);
    }
  });

  return ids;
}

/**
 * Check if a node is a mediaImage with upload in progress.
 */
export function isMediaUploadInProgress(node: ProseMirrorNode): boolean {
  return node.type.name === "mediaImage" && node.attrs?.mediaId === null;
}

/**
 * Get the depth level of a heading, or null if not a heading.
 */
export function getHeadingLevel(editor: Editor): number | null {
  const attrs = editor.getAttributes("heading");
  return attrs.level ?? null;
}

/**
 * Create a list of all active marks at the cursor.
 * Useful for toolbar state tracking.
 */
export function getActiveMarks(editor: Editor): string[] {
  const marks: string[] = [];
  const markTypes = editor.schema.marks;

  for (const markName in markTypes) {
    if (editor.isActive(markName)) {
      marks.push(markName);
    }
  }

  return marks;
}

/**
 * Get all active block types at the cursor.
 * Some editors support multiple (e.g., nested lists).
 */
export function getActiveBlocks(editor: Editor): string[] {
  const blocks: string[] = [];
  const nodeTypes = editor.schema.nodes;

  for (const nodeName in nodeTypes) {
    if (editor.isActive(nodeName)) {
      blocks.push(nodeName);
    }
  }

  return blocks;
}

/**
 * Check if the current position allows inserting media.
 * Media typically only goes in paragraphs, not inside marks.
 */
export function canInsertMediaAtCursor(editor: Editor): boolean {
  const { $from } = editor.state.selection;
  const node = $from.parent;

  // Media can go in paragraphs, list items, blockquotes, etc.
  const allowedParents = ["paragraph", "listItem", "blockquote"];
  return allowedParents.includes(node.type.name);
}

/**
 * Validate that editor content is valid JSON.
 * Useful before saving.
 */
export function isEditorContentValid(editor: Editor): boolean {
  try {
    const json = editor.getJSON();
    return json && typeof json === "object" && json.type === "doc";
  } catch {
    return false;
  }
}

/**
 * Get plaintext version of editor content.
 */
export function getEditorPlaintext(editor: Editor): string {
  return editor.getText();
}

/**
 * Check if editor is completely empty (no content).
 */
export function isEditorEmpty(editor: Editor): boolean {
  const text = editor.getText().trim();
  const mediaNodes = extractMediaNodes(editor);
  return text.length === 0 && mediaNodes.length === 0;
}
