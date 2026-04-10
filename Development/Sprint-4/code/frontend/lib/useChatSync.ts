"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import { useChatThreads, useDeleteChatThread, useUpsertChatThread } from "@/lib/hooks";
import type { ChartSpecV1 } from "@/lib/types/chartspec";
import { useAppStore, type ChatMode, type ChatThreadState, type ChatTurn } from "@/lib/store";
import {
  buildChatThreadSnapshots,
  diffChatThreadSnapshots,
  indexChatThreadSnapshots,
  mergeHydratedChatThreads,
  shouldEnableChatSync,
  type ChatThreadSnapshot,
} from "@/lib/chat-sync-core";

interface UseChatSyncOptions {
  enabled?: boolean;
}

function toSnapshotThreadKeyMap(threads: ReadonlyArray<ChatThreadSnapshot>) {
  return indexChatThreadSnapshots(threads);
}

export function useChatSync(options: UseChatSyncOptions = {}) {
  const enabled = shouldEnableChatSync(options.enabled ?? true);
  const {
    chatTurnsByKey,
    chatStateByKey,
    lastChartSpecByKey,
    savedPromptsByKey,
    chatMode,
    hydrateChatThreads,
  } = useAppStore();

  const localThreads = useMemo(
    () =>
      buildChatThreadSnapshots({
        chatTurnsByKey,
        chatStateByKey,
        lastChartSpecByKey,
        savedPromptsByKey,
        chatMode,
      }),
    [chatMode, chatStateByKey, chatTurnsByKey, lastChartSpecByKey, savedPromptsByKey],
  );
  const localThreadMap = useMemo(() => toSnapshotThreadKeyMap(localThreads), [localThreads]);

  const { data: backendThreads = [], isFetched } = useChatThreads({ enabled });
  const upsertMutation = useUpsertChatThread();
  const deleteMutation = useDeleteChatThread();

  const hydratedRef = useRef(false);
  const skipNextSyncRef = useRef(false);
  const prevSnapshotRef = useRef<Record<string, ChatThreadSnapshot>>({});
  const dirtyKeysRef = useRef<Set<string>>(new Set());
  const deletedKeysRef = useRef<Set<string>>(new Set());
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasEnabledRef = useRef(enabled);

  const backendSnapshots = useMemo<ChatThreadSnapshot[]>(
    () =>
      backendThreads.map((thread) => ({
        thread_key: thread.thread_key,
        turns: thread.turns,
        chat_state: thread.chat_state,
        last_chart_spec: thread.last_chart_spec,
        saved_prompts: thread.saved_prompts,
        chat_mode: thread.chat_mode || "auto",
      })),
    [backendThreads],
  );

  const flushPendingSync = useCallback(() => {
    if (!hydratedRef.current) {
      return;
    }

    const deletedKeys = Array.from(deletedKeysRef.current);
    const dirtyKeys = Array.from(dirtyKeysRef.current);

    deletedKeysRef.current.clear();
    dirtyKeysRef.current.clear();

    for (const threadKey of deletedKeys) {
      deleteMutation.mutate(threadKey);
    }

    for (const threadKey of dirtyKeys) {
      const thread = localThreadMap[threadKey];
      if (!thread || thread.turns.length === 0) {
        continue;
      }
      upsertMutation.mutate({
        thread_key: thread.thread_key,
        turns: thread.turns as Record<string, unknown>[],
        chat_state: thread.chat_state,
        last_chart_spec: thread.last_chart_spec,
        saved_prompts: thread.saved_prompts,
        chat_mode: thread.chat_mode,
      });
    }
  }, [deleteMutation, localThreadMap, upsertMutation]);

  useEffect(() => {
    if (!enabled || !isFetched || hydratedRef.current) {
      return;
    }

    const mergedThreads = mergeHydratedChatThreads({
      localThreads,
      remoteThreads: backendSnapshots,
    });

    hydratedRef.current = true;
    skipNextSyncRef.current = true;
    prevSnapshotRef.current = toSnapshotThreadKeyMap(mergedThreads);
    dirtyKeysRef.current.clear();
    deletedKeysRef.current.clear();

    hydrateChatThreads(
      mergedThreads.map((thread) => ({
        thread_key: thread.thread_key,
        turns: thread.turns as ChatTurn[],
        chat_state: (thread.chat_state as ChatThreadState | null) ?? null,
        last_chart_spec: (thread.last_chart_spec as ChartSpecV1 | null) ?? null,
        saved_prompts: thread.saved_prompts,
        chat_mode: (thread.chat_mode === "chart" || thread.chat_mode === "explain" ? thread.chat_mode : "auto") as ChatMode,
      })),
    );
  }, [backendSnapshots, enabled, hydrateChatThreads, isFetched, localThreads]);

  useEffect(() => {
    if (!hydratedRef.current) {
      return;
    }

    const diff = diffChatThreadSnapshots(prevSnapshotRef.current, localThreadMap);
    if (diff.dirtyKeys.length === 0 && diff.deletedKeys.length === 0) {
      return;
    }

    for (const threadKey of diff.deletedKeys) {
      deletedKeysRef.current.add(threadKey);
      dirtyKeysRef.current.delete(threadKey);
    }

    for (const threadKey of diff.dirtyKeys) {
      dirtyKeysRef.current.add(threadKey);
      deletedKeysRef.current.delete(threadKey);
    }

    prevSnapshotRef.current = localThreadMap;
  }, [localThreadMap]);

  useEffect(() => {
    if (!enabled || !hydratedRef.current) {
      return;
    }

    if (skipNextSyncRef.current) {
      skipNextSyncRef.current = false;
      return;
    }

    if (dirtyKeysRef.current.size === 0 && deletedKeysRef.current.size === 0) {
      return;
    }

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      flushPendingSync();
    }, 1500);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [enabled, flushPendingSync, localThreadMap]);

  useEffect(() => {
    if (wasEnabledRef.current && !enabled) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      flushPendingSync();
    }
    wasEnabledRef.current = enabled;
  }, [enabled, flushPendingSync]);

  useEffect(
    () => () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      flushPendingSync();
    },
    [flushPendingSync],
  );
}
