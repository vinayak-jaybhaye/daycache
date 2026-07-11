"use client";

import { useEffect } from "react";
import { ScrapbookView } from "@/features/ScrapbookView";
import { useJournalStore } from "@/store/useJournalStore";

export default function FavoritesPage() {
  const { setFilter } = useJournalStore();

  useEffect(() => {
    setFilter({ type: "favorite" });
  }, [setFilter]);

  return <ScrapbookView title="Favorites" description="Your most cherished memories." />;
}
