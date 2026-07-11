"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { useUserStore } from "@/store/useUserStore";
import { DoodleStar } from "@/components/Doodles";

export const AuthView = () => {
  const { login, register } = useUserStore();

  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password, displayName);
        // After registration, login automatically
        await login(email, password);
      }
      window.location.href = "/";
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden px-4 pt-8 pb-16 sm:px-6 sm:pt-12 sm:pb-24"
    >
      <DoodleStar className="absolute top-40 left-[10%] scale-150 text-[var(--ink-color)] opacity-20" />
      <DoodleStar className="absolute right-[15%] bottom-40 scale-125 text-[var(--ink-color)] opacity-20" />

      <div className="paper-card relative z-10 w-full max-w-md rounded-2xl p-6 sm:p-10">
        <div className="mb-8 text-center">
          <h2 className="mb-2 font-serif text-4xl text-[var(--ink-color)]">DayCache</h2>
          <p className="font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
            {isLogin ? "Welcome Back" : "Begin Your Journey"}
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-center font-sans text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {!isLogin && (
            <div>
              <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required={!isLogin}
                className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] transition-colors outline-none focus:border-[var(--accent-color)]"
                placeholder="How should we call you?"
              />
            </div>
          )}

          <div>
            <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] transition-colors outline-none focus:border-[var(--accent-color)]"
              placeholder="your@email.com"
            />
          </div>

          <div>
            <label className="mb-2 block font-sans text-xs tracking-widest text-[var(--text-muted)] uppercase">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full border-b border-[var(--border-soft)] bg-transparent py-2 font-serif text-lg text-[var(--ink-color)] transition-colors outline-none focus:border-[var(--accent-color)]"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-4 w-full rounded-full bg-[var(--ink-color)] py-3 font-sans text-sm tracking-widest text-[var(--bg-color)] uppercase transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Processing..." : isLogin ? "Sign In" : "Create Account"}
          </button>
        </form>

        <div className="mt-8 text-center">
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError("");
            }}
            className="font-sans text-xs text-[var(--text-muted)] transition-colors hover:text-[var(--ink-color)]"
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </motion.div>
  );
};
