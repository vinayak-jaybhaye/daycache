"use client";

import React, { useEffect } from "react";
import { useParams } from "next/navigation";
import { ScrapbookView } from "@/features/ScrapbookView";
import { useJournalStore } from "@/store/useJournalStore";
import { useTagStore } from "@/store/useTagStore";

export default function TagPage() {
  const params = useParams();
  const id = params?.id as string;
  const { setFilter } = useJournalStore();
  const { tags } = useTagStore();

  const tag = tags.find((t) => t.id === id);

  useEffect(() => {
    if (id) {
      setFilter({ type: "tag", id });
    }
  }, [id, setFilter]);

  if (!tag) {
    return <ScrapbookView title="Tag not found" description="" />;
  }

  return <ScrapbookView title={tag.name} description={`Entries tagged with #${tag.name}`} />;
}
