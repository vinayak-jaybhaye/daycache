"use client";

import { ScrapbookView } from "@/features/ScrapbookView";
import { useUIStore } from "@/store/useUIStore";

export default function Page() {
  const { currentView } = useUIStore();

  // For Step 1, keep the client routing logic here to ensure it doesn't break yet.
  // As we move views to their own routes, we will replace this entirely.
  if (currentView === "home") return <ScrapbookView />;
  return <ScrapbookView />;
}
