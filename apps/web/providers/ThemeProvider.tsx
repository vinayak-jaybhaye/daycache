"use client";

import React, { useEffect } from "react";
import { useUserStore } from "@/store/useUserStore";
import { Playfair_Display, Inter, Caveat } from "next/font/google";

const playfair = Playfair_Display({ subsets: ["latin"], variable: "--font-serif" });
const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const caveat = Caveat({ subsets: ["latin"], variable: "--font-hand" });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { settings } = useUserStore();

  useEffect(() => {
    // Apply theme data-attribute
    document.documentElement.setAttribute("data-theme", settings?.theme || "morning");

    // Apply editor font as a variable if it's dynamic,
    // but we use the Google Fonts classes on the body for standard typography.
  }, [settings?.theme, settings?.editor_font]);

  return (
    <div
      className={`${playfair.variable} ${inter.variable} ${caveat.variable} font-sans`}
      style={{ width: "100%", minHeight: "100vh" }}
    >
      {children}
    </div>
  );
}
