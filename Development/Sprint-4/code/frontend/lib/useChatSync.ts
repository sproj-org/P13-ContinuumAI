"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import type { ChatTurn, ChatThreadState, ChatMode } from "@/lib/store";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import { useChatThreads, useUpsertChatThread, useDeleteChatThread } from "@/lib/hooks";

/**
 * Bidirectional sync between Zustand chat state and the backend.
 *
 * 1. On mount  → fetch all threads from DB → hydrate Zustand store.
 * 2. On change → debounce-upsert the affected thread(s) back to DB.
 * 3. On clear  → delete the thread from DB.
 *
 * Drop this hook once inside the workspace page and forget about it.
 */
export function useChatSync() {
  const {
    chatTurnsByKey,
    chatStateByKey,
    lastChartSpecByKey,
    savedPromptsByKey,
    chatMode,
    hydrateChatThreads,
  } = useAppStore();

  // ── Backend hooks ──────────────────────────────────────
  const { data: backendThreads } = useChatThreads();
  const upsertMutation = useUpsertChatThread();
  const deleteMutation = useDeleteChatThread();

  // Track whether we've done the initial hydration so we don't
  // keep overwriting local edits every time the query refetches.
  const hydratedRef = useRef(false);

  // Skip the very first sync-back that fires right after hydration
  // (it would just re-upload the same data we just fetched).
  const skipNextSyncRef = useRef(false);

  // Keep a snapshot of keys we know exist so we can detect deletions.
  const prevKeysRef = useRef<Set<string>>(new Set());

  // ── 1. Hydrate store from backend on first fetch ──────
  useEffect(() => {
    if (!backendThreads || hydratedRef.current) return;
    hydratedRef.current = true;
    skipNextSyncRef.current = true;

    const threads = backendThreads.map((t) => ({
      thread_key: t.thread_key,
      turns: t.turns as unknown as ChatTurn[],
      chat_state: t.chat_state as unknown as ChatThreadState | null,
      last_chart_spec: t.last_chart_spec as unknown as ChartSpecV1 | null,
      saved_prompts: t.saved_prompts,
      chat_mode: (t.chat_mode || "auto") as ChatMode,
    }));

    // ALWAYS hydrate — even when empty — so stale local data from a
    // previous user's session is wiped and the DB stays source-of-truth.
    hydrateChatThreads(threads);

    // Seed prevKeys
    prevKeysRef.current = new Set(threads.map((t) => t.thread_key));
  }, [backendThreads, hydrateChatThreads]);

  // ── 2. Debounced sync back to backend ─────────────────
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const syncToBackend = useCallback(() => {
    const currentKeys = new Set(Object.keys(chatTurnsByKey));

    // Detect deleted keys → delete from backend
    for (const prevKey of prevKeysRef.current) {
      if (!currentKeys.has(prevKey)) {
        deleteMutation.mutate(prevKey);
      }
    }

    // Upsert all current threads
    for (const key of currentKeys) {
      const turns = chatTurnsByKey[key];
      // Skip empty threads (no turns yet)
      if (!turns || turns.length === 0) continue;

      upsertMutation.mutate({
        thread_key: key,
        turns: turns as unknown as Record<string, unknown>[],
        chat_state: (chatStateByKey[key] ?? null) as unknown as Record<string, unknown> | null,
        last_chart_spec: (lastChartSpecByKey[key] ?? null) as unknown as Record<string, unknown> | null,
        saved_prompts: savedPromptsByKey[key] ?? [],
        chat_mode: chatMode,
      });
    }

    prevKeysRef.current = currentKeys;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatTurnsByKey, chatStateByKey, lastChartSpecByKey, savedPromptsByKey, chatMode]);

  useEffect(() => {
    // Don't sync until initial hydration is done
    if (!hydratedRef.current) return;

    // Skip the sync that fires right after hydration (no real changes)
    if (skipNextSyncRef.current) {
      skipNextSyncRef.current = false;
      return;
    }

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(syncToBackend, 1500); // 1.5s debounce

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [syncToBackend]);
}
