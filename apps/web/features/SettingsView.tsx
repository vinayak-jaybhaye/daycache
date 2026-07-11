"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  Settings,
  User,
  Palette,
  Type,
  Globe,
  Clock,
  Bot,
  X,
  Smartphone,
  Trash2,
  LogOut,
} from "lucide-react";
import { useUserStore } from "@/store/useUserStore";
import type { Theme } from "@/lib/api/users";
import type { DeviceSessionResponse } from "@/lib/api/auth";

export const SettingsView = () => {
  const {
    profile,
    settings,
    devices,
    updateProfile,
    updateSettings,
    availablePersonas,
    fetchPersonas,
    uploadAvatar,
    removeAvatar,
    deleteAccount,
    revokeSession,
    revokeOtherSessions,
    logout,
  } = useUserStore();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    fetchPersonas();
  }, [fetchPersonas]);

  if (!profile || !settings) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8 }}
      className="relative mx-auto min-h-screen w-full max-w-3xl px-4 pt-20 pb-32 sm:px-6 sm:pt-24 sm:pb-48 md:px-12"
    >
      <div className="mb-12 flex items-center gap-4 border-b border-[var(--border-soft)] pb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--ink-color)] text-[var(--bg-color)]">
          <Settings size={18} />
        </div>
        <div>
          <h2 className="font-serif text-2xl text-[var(--ink-color)] sm:text-3xl">Settings</h2>
          <p className="font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
            Profile & Preferences
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-12">
        {/* Profile Section */}
        <section>
          <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-[var(--ink-color)]">
            <User size={18} className="text-[var(--text-muted)]" /> Account
          </h3>
          <div className="glass-panel flex flex-col gap-6 rounded-2xl border border-[var(--border-soft)] p-6">
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:gap-6">
              <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full border-2 border-[var(--bg-color)] bg-[var(--border-soft)] shadow-sm">
                {profile.avatar_url ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={profile.avatar_url}
                    alt={profile.display_name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <User size={32} className="text-[var(--text-muted)]" />
                )}
              </div>
              <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  accept="image/png, image/jpeg, image/webp"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      try {
                        await uploadAvatar(file);
                      } catch (err: unknown) {
                        const errorObj = err as {
                          response?: { data?: { detail?: string } };
                          message?: string;
                        };
                        alert(
                          errorObj.response?.data?.detail ||
                            errorObj.message ||
                            "Failed to upload avatar.",
                        );
                      }
                    }
                  }}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-full border border-[var(--border-soft)] px-4 py-2 font-sans text-xs tracking-widest text-[var(--ink-color)] uppercase transition-colors hover:bg-[var(--border-soft)]"
                >
                  Change Avatar
                </button>
                {profile.avatar_url && (
                  <button
                    onClick={removeAvatar}
                    className="rounded-full border border-[var(--border-soft)] p-2 text-red-500 transition-colors hover:bg-red-500/10"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                  Display Name
                </label>
                <input
                  type="text"
                  value={profile.display_name}
                  onChange={(e) => updateProfile({ display_name: e.target.value })}
                  className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] transition-colors outline-none focus:border-[var(--accent-color)]"
                />
              </div>
              <div>
                <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                  Email
                </label>
                <input
                  type="text"
                  value={profile.email}
                  disabled
                  className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--text-muted)] opacity-70 outline-none"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Preferences Section */}
        <section>
          <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-[var(--ink-color)]">
            <Palette size={18} className="text-[var(--text-muted)]" /> Appearance
          </h3>
          <div className="glass-panel grid grid-cols-1 gap-8 rounded-2xl border border-[var(--border-soft)] p-6 md:grid-cols-2">
            <div>
              <label className="mb-4 block flex items-center gap-2 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                <Palette size={14} /> Theme
              </label>
              <div className="flex flex-col gap-3">
                {["morning", "midnight", "forest", "cinematic"].map((t) => (
                  <label key={t} className="group flex cursor-pointer items-center gap-3">
                    <input
                      type="radio"
                      name="theme"
                      checked={settings.theme === t}
                      onChange={() =>
                        updateSettings({
                          theme: t as Theme,
                        })
                      }
                      className="hidden"
                    />
                    <div
                      className={`flex h-4 w-4 items-center justify-center rounded-full border transition-colors ${settings.theme === t ? "border-[var(--accent-color)]" : "border-[var(--text-muted)] group-hover:border-[var(--ink-color)]"}`}
                    >
                      {settings.theme === t && (
                        <div className="h-2 w-2 rounded-full bg-[var(--accent-color)]" />
                      )}
                    </div>
                    <span className="font-serif text-lg text-[var(--ink-color)] capitalize">
                      {t}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-4 block flex items-center gap-2 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                <Type size={14} /> Editor Font
              </label>
              <div className="flex flex-col gap-3">
                {(["Serif", "Inter", "Caveat"] as const).map((f) => (
                  <label key={f} className="group flex cursor-pointer items-center gap-3">
                    <input
                      type="radio"
                      name="font"
                      checked={settings.editor_font === f}
                      onChange={() => updateSettings({ editor_font: f })}
                      className="hidden"
                    />
                    <div
                      className={`flex h-4 w-4 items-center justify-center rounded-full border transition-colors ${settings.editor_font === f ? "border-[var(--accent-color)]" : "border-[var(--text-muted)] group-hover:border-[var(--ink-color)]"}`}
                    >
                      {settings.editor_font === f && (
                        <div className="h-2 w-2 rounded-full bg-[var(--accent-color)]" />
                      )}
                    </div>
                    <span
                      className="font-serif text-lg text-[var(--ink-color)]"
                      style={{
                        fontFamily:
                          f === "Inter"
                            ? "var(--font-sans)"
                            : f === "Caveat"
                              ? "var(--font-hand)"
                              : "var(--font-serif)",
                      }}
                    >
                      {f}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* General & AI Section */}
        <section>
          <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-[var(--ink-color)]">
            <Bot size={18} className="text-[var(--text-muted)]" /> General & AI
          </h3>
          <div className="glass-panel grid grid-cols-1 gap-6 rounded-2xl border border-[var(--border-soft)] p-6 md:grid-cols-2">
            <div>
              <label className="mb-2 block flex items-center gap-2 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                <Globe size={14} /> Locale
              </label>
              <input
                type="text"
                value={settings.locale}
                onChange={(e) => updateSettings({ locale: e.target.value })}
                className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] outline-none focus:border-[var(--accent-color)]"
              />
            </div>
            <div>
              <label className="mb-2 block flex items-center gap-2 font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                <Clock size={14} /> Timezone
              </label>
              <input
                type="text"
                value={settings.timezone}
                onChange={(e) => updateSettings({ timezone: e.target.value })}
                className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] outline-none focus:border-[var(--accent-color)]"
              />
            </div>
            <div className="pt-4 md:col-span-2">
              <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                AI Persona
              </label>
              <select
                value={settings.ai_persona_name || ""}
                onChange={(e) => updateSettings({ ai_persona_name: e.target.value })}
                className="w-full cursor-pointer appearance-none border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] outline-none focus:border-[var(--accent-color)]"
              >
                {availablePersonas.length === 0 && (
                  <option value="Mira" className="bg-[var(--bg-color)]">
                    Mira (Default)
                  </option>
                )}
                {availablePersonas.map((persona) => (
                  <option key={persona.name} value={persona.name} className="bg-[var(--bg-color)]">
                    {persona.name} — {persona.tagline}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>
        {/* Security & Sessions */}
        <section>
          <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-[var(--ink-color)]">
            <Smartphone size={18} className="text-[var(--text-muted)]" /> Security & Sessions
          </h3>
          <div className="glass-panel flex flex-col gap-6 rounded-2xl border border-[var(--border-soft)] p-6">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                Devices & Sessions
              </span>
              {devices.reduce((acc, dev) => acc + dev.sessions.length, 0) > 1 && (
                <button
                  onClick={revokeOtherSessions}
                  className="text-xs text-[var(--accent-color)] hover:underline"
                >
                  Revoke all others
                </button>
              )}
            </div>

            <div className="flex flex-col gap-6">
              {devices.map((device) => (
                <div
                  key={device.id}
                  className="overflow-hidden rounded-xl border border-[var(--border-soft)]"
                >
                  <div className="flex flex-col items-start gap-2 bg-[var(--border-soft)]/50 p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
                    <h4 className="font-serif text-lg text-[var(--ink-color)]">
                      {device.name || "Unknown Device"}{" "}
                      <span className="ml-2 font-sans text-sm text-[var(--text-muted)]">
                        ({device.platform})
                      </span>
                    </h4>
                  </div>
                  <div className="flex flex-col gap-3 p-4">
                    {device.sessions.map((session: DeviceSessionResponse) => (
                      <div
                        key={session.id}
                        className="flex flex-col gap-2 border-b border-[var(--border-soft)] pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <p className="flex items-center gap-2 font-sans text-sm text-[var(--ink-color)]">
                            Session{" "}
                            {session.is_current && (
                              <span className="rounded-full bg-[var(--accent-color)]/20 px-2 py-1 font-sans text-xs tracking-widest text-[var(--accent-color)] uppercase">
                                Current
                              </span>
                            )}
                          </p>
                          <p className="mt-1 font-sans text-xs tracking-widest text-[var(--text-muted)]">
                            {session.created_ip || "Unknown IP"} • Last active:{" "}
                            {new Date(session.last_used_at).toLocaleDateString()}
                          </p>
                        </div>
                        {!session.is_current && (
                          <button
                            onClick={() => revokeSession(session.id)}
                            className="rounded-full p-2 text-red-500 transition-colors hover:bg-red-500/10"
                            title="Revoke session"
                          >
                            <LogOut size={16} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Account Actions & Danger Zone */}
        <section className="mb-24 flex flex-col gap-12">
          <div>
            <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-[var(--ink-color)]">
              <LogOut size={18} className="text-[var(--text-muted)]" /> Account Actions
            </h3>
            <div className="glass-panel flex flex-col items-start justify-between gap-4 rounded-2xl border border-[var(--border-soft)] p-6 sm:flex-row sm:items-center">
              <div>
                <h4 className="font-serif text-lg text-[var(--ink-color)]">Log Out</h4>
                <p className="mt-1 font-sans text-xs tracking-wide text-[var(--text-muted)]">
                  Log out of your current session on this device.
                </p>
              </div>
              <button
                onClick={() => {
                  if (confirm("Are you sure you want to log out?")) {
                    logout();
                  }
                }}
                className="rounded-full border border-[var(--border-soft)] px-6 py-2 font-sans text-xs tracking-widest whitespace-nowrap text-[var(--ink-color)] uppercase transition-colors hover:bg-[var(--border-soft)]"
              >
                Log Out
              </button>
            </div>
          </div>

          <div>
            <h3 className="mb-6 flex items-center gap-2 font-serif text-xl text-red-500">
              <Trash2 size={18} /> Danger Zone
            </h3>
            <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-500/20 bg-red-500/5 p-6 sm:flex-row sm:items-center">
              <div>
                <h4 className="font-serif text-lg text-[var(--ink-color)]">Delete Account</h4>
                <p className="mt-1 font-sans text-xs tracking-wide text-[var(--text-muted)]">
                  Permanently delete your account and all your memories. This action cannot be
                  undone.
                </p>
              </div>
              <button
                onClick={() => {
                  if (
                    confirm(
                      "Are you absolutely sure you want to delete your account? This action cannot be undone.",
                    )
                  ) {
                    deleteAccount();
                  }
                }}
                className="rounded-full bg-red-500 px-6 py-2 font-sans text-xs tracking-widest whitespace-nowrap text-white uppercase transition-colors hover:bg-red-600"
              >
                Delete Account
              </button>
            </div>
          </div>
        </section>
      </div>
    </motion.div>
  );
};
