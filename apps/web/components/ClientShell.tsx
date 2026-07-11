"use client";

import React from "react";
import { Sidebar } from "./Sidebar";
import { useUIStore } from "@/store/useUIStore";
import { useUserStore } from "@/store/useUserStore";

import { useJournalStore } from "@/store/useJournalStore";

export function ClientShell({ children }: { children: React.ReactNode }) {
  const { isSidebarOpen } = useUIStore();
  const { isAuthenticated, fetchMe } = useUserStore();
  const { fetchEntries, fetchMoods } = useJournalStore();
  const initialized = React.useRef(false);

  React.useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchMe();
    }
  }, [fetchMe]);

  React.useEffect(() => {
    if (isAuthenticated) {
      fetchEntries(true);
      fetchMoods();
    }
  }, [isAuthenticated, fetchEntries, fetchMoods]);

  return (
    <div className="relative flex min-h-screen w-full overflow-x-hidden bg-[var(--bg-color)]">
      {isAuthenticated && <Sidebar />}
      <div
        className={`relative flex flex-1 flex-col transition-all duration-300 ${
          isAuthenticated && isSidebarOpen ? "md:ml-64" : ""
        }`}
      >
        {children}
      </div>
    </div>
  );
}
