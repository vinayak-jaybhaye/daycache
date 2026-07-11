/**
 * EditorService — High-level operations on the editor.
 *
 * Provides a clean API for common editor operations.
 * Useful for components and hooks that need to interact with the editor
 * without directly accessing the TipTap API.
 */

import type { Editor } from "@tiptap/core";
import {
  extractMediaIds,
  extractMediaNodes,
  isEditorEmpty,
  getEditorPlaintext,
  isInBlockType,
} from "../utils/editorHelpers";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";

/**
 * EditorService — Stateless service for editor operations.
 */
export class EditorService {
  /**
   * Get all media IDs in the document.
   * Useful for backend reconciliation on save.
   */
  static getMediaIds(editor: Editor): string[] {
    return extractMediaIds(editor);
  }

  /**
   * Get all media nodes in the document with positions.
   */
  static getMediaNodes(editor: Editor): Array<{
    pos: number;
    node: ProseMirrorNode;
    attrs: Record<string, unknown>;
  }> {
    return extractMediaNodes(editor);
  }

  /**
   * Get the document as clean JSON (without transient upload state).
   */
  static getDocumentJSON(editor: Editor): Record<string, unknown> {
    return editor.getJSON();
  }

  /**
   * Get plaintext version of the document.
   */
  static getPlaintext(editor: Editor): string {
    return getEditorPlaintext(editor);
  }

  /**
   * Check if the document is empty.
   */
  static isEmpty(editor: Editor): boolean {
    return isEditorEmpty(editor);
  }

  /**
   * Replace the entire document content.
   */
  static setContent(editor: Editor, content: string | Record<string, unknown>) {
    editor.commands.setContent(content);
  }

  /**
   * Clear all content from the editor.
   */
  static clear(editor: Editor) {
    editor.commands.clearContent();
  }

  /**
   * Focus the editor.
   */
  static focus(editor: Editor) {
    editor.chain().focus().run();
  }

  /**
   * Get the cursor position in the document.
   */
  static getCursorPosition(editor: Editor): number {
    return editor.state.selection.from;
  }

  /**
   * Move cursor to a specific position.
   */
  static setCursorPosition(editor: Editor, pos: number) {
    editor.chain().focus().setTextSelection(Math.max(0, pos)).run();
  }

  /**
   * Get selected text.
   */
  static getSelectedText(editor: Editor): string {
    const { from, to } = editor.state.selection;
    return editor.state.doc.textBetween(from, to, " ");
  }

  /**
   * Get character count.
   */
  static getCharacterCount(editor: Editor): number {
    return editor.state.doc.content.size;
  }

  /**
   * Get word count.
   */
  static getWordCount(editor: Editor): number {
    const text = editor.getText();
    return text.split(/\s+/).filter((word) => word.length > 0).length;
  }

  /**
   * Insert text at cursor.
   */
  static insertText(editor: Editor, text: string) {
    editor.chain().focus().insertContent(text).run();
  }

  /**
   * Insert a node at cursor.
   */
  static insertNode(editor: Editor, node: Record<string, unknown> | string) {
    editor.chain().focus().insertContent(node).run();
  }

  /**
   * Delete selected content.
   */
  static deleteSelection(editor: Editor) {
    editor.chain().focus().deleteSelection().run();
  }

  /**
   * Select all content.
   */
  static selectAll(editor: Editor) {
    editor.chain().focus().selectAll().run();
  }

  /**
   * Undo the last action.
   */
  static undo(editor: Editor) {
    if (editor.can().undo()) {
      editor.chain().undo().run();
    }
  }

  /**
   * Redo the last undone action.
   */
  static redo(editor: Editor) {
    if (editor.can().redo()) {
      editor.chain().redo().run();
    }
  }

  /**
   * Check if undo is available.
   */
  static canUndo(editor: Editor): boolean {
    return editor.can().undo();
  }

  /**
   * Check if redo is available.
   */
  static canRedo(editor: Editor): boolean {
    return editor.can().redo();
  }

  /**
   * Check if current position is in a specific block type.
   */
  static isInBlock(editor: Editor, blockType: string): boolean {
    return isInBlockType(editor, blockType);
  }

  /**
   * Get heading level if in a heading block.
   */
  static getHeadingLevel(editor: Editor): number | null {
    const attrs = editor.getAttributes("heading");
    return attrs.level ?? null;
  }

  /**
   * Create a snapshot of the current document state.
   * Useful for implementing custom undo/redo or collaboration.
   */
  static createSnapshot(editor: Editor) {
    return {
      content: editor.getJSON(),
      plaintext: editor.getText(),
      timestamp: Date.now(),
      cursorPos: editor.state.selection.from,
    };
  }

  /**
   * Restore from a snapshot.
   */
  static restoreFromSnapshot(
    editor: Editor,
    snapshot: { content: Record<string, unknown>; cursorPos: number },
  ) {
    editor.commands.setContent(snapshot.content);
    editor.chain().focus().setTextSelection(snapshot.cursorPos).run();
  }

  /**
   * Get editor statistics.
   */
  static getStatistics(editor: Editor) {
    return {
      characters: this.getCharacterCount(editor),
      words: this.getWordCount(editor),
      paragraphs: (editor.getText().match(/\n/g) || []).length + 1,
      mediaCount: this.getMediaIds(editor).length,
      isEmpty: this.isEmpty(editor),
    };
  }
}
