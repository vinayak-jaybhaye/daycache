import type { JSONContent } from "@tiptap/core";

export const EMPTY_DOCUMENT: JSONContent = {
  type: "doc",
  content: [{ type: "paragraph" }],
};

export function isTiptapDocument(value: unknown): value is JSONContent {
  return Boolean(value && typeof value === "object" && (value as JSONContent).type === "doc");
}

export function normalizeEditorContent(
  content: Record<string, unknown> | null | undefined,
  fallbackText?: string | null,
): JSONContent | string {
  if (isTiptapDocument(content)) {
    return content;
  }

  if (typeof content?.text === "string") {
    return content.text;
  }

  return fallbackText || EMPTY_DOCUMENT;
}

export function prepareContentForSave(content: JSONContent): JSONContent {
  return pruneNode(content) ?? EMPTY_DOCUMENT;
}

export function extractMediaIds(content: JSONContent): string[] {
  const ids = new Set<string>();

  walkContent(content, (node) => {
    if (node.type === "mediaImage" && typeof node.attrs?.mediaId === "string") {
      ids.add(node.attrs.mediaId);
    }
  });

  return Array.from(ids);
}

function pruneNode(node: JSONContent): JSONContent | null {
  if (node.type === "mediaImage") {
    const mediaId = stringOrNull(node.attrs?.mediaId);
    const src = stringOrNull(node.attrs?.src);

    if (!mediaId && !src) {
      return null;
    }

    return {
      ...node,
      attrs: compactAttrs({
        mediaId,
        src,
        alt: stringOrEmpty(node.attrs?.alt),
        title: stringOrEmpty(node.attrs?.title),
      }),
    };
  }

  const children = node.content?.map(pruneNode).filter(Boolean) as JSONContent[] | undefined;
  const attrs = node.attrs ? compactAttrs({ ...node.attrs, uploadId: undefined }) : undefined;

  return {
    ...node,
    ...(attrs ? { attrs } : {}),
    ...(children ? { content: children } : {}),
  };
}

function walkContent(node: JSONContent, visitor: (node: JSONContent) => void) {
  visitor(node);
  node.content?.forEach((child) => walkContent(child, visitor));
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function stringOrEmpty(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function compactAttrs(attrs: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(attrs).filter(([, value]) => value !== undefined && value !== null),
  );
}
