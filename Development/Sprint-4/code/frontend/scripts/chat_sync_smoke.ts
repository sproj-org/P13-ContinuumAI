import assert from "node:assert/strict";

import {
  buildChatThreadSnapshots,
  deleteChatThreadCache,
  diffChatThreadSnapshots,
  indexChatThreadSnapshots,
  mergeHydratedChatThreads,
  shouldEnableChatSync,
  upsertChatThreadCache,
  type ChatThreadSnapshot,
} from "../lib/chat-sync-core";

function makeThread(overrides: Partial<ChatThreadSnapshot> = {}): ChatThreadSnapshot {
  return {
    thread_key: overrides.thread_key ?? "silkroute:sales",
    turns: overrides.turns ?? [{ role: "user", message: "Show sales" }],
    chat_state: overrides.chat_state ?? null,
    last_chart_spec: overrides.last_chart_spec ?? null,
    saved_prompts: overrides.saved_prompts ?? [],
    chat_mode: overrides.chat_mode ?? "chart",
  };
}

function run() {
  assert.equal(shouldEnableChatSync(false), false, "chat sync must stay disabled outside VizAgent");
  assert.equal(shouldEnableChatSync(true), true, "chat sync must enable when VizAgent opens");

  const localThreads = buildChatThreadSnapshots({
    chatTurnsByKey: {
      "silkroute:sales": [{ role: "user", message: "Show sales by region" }],
      "silkroute:returns": [{ role: "user", message: "Explain return rate" }],
    },
    chatStateByKey: {
      "silkroute:sales": { clarify_id: null, selections: {}, original_user_intent: "Show sales by region" },
      "silkroute:returns": { clarify_id: null, selections: {}, original_user_intent: "Explain return rate" },
    },
    lastChartSpecByKey: {
      "silkroute:sales": { mark: "bar" },
      "silkroute:returns": { mark: "line" },
    },
    savedPromptsByKey: {
      "silkroute:sales": ["Show sales by region"],
      "silkroute:returns": ["Explain return rate"],
    },
    chatModeByKey: {
      "silkroute:sales": "chart",
      "silkroute:returns": "explain",
    },
  });
  assert.equal(
    localThreads.find((thread) => thread.thread_key === "silkroute:sales")?.chat_mode,
    "chart",
    "thread snapshots must preserve the active chat mode for chart-oriented threads",
  );
  assert.equal(
    localThreads.find((thread) => thread.thread_key === "silkroute:returns")?.chat_mode,
    "explain",
    "thread snapshots must preserve per-thread explain mode",
  );

  const remoteThreads = [
    makeThread({
      thread_key: "silkroute:sales",
      turns: [{ role: "user", message: "Older remote copy" }],
      chat_mode: "auto",
    }),
    makeThread({
      thread_key: "silkroute:inventory",
      turns: [{ role: "user", message: "Show inventory" }],
      chat_mode: "chart",
    }),
  ];

  const mergedThreads = mergeHydratedChatThreads({
    localThreads,
    remoteThreads,
  });
  assert.equal(mergedThreads.length, 3, "hydration should preserve remote-only threads");
  assert.equal(
    mergedThreads.find((thread) => thread.thread_key === "silkroute:sales")?.turns[0],
    localThreads.find((thread) => thread.thread_key === "silkroute:sales")?.turns[0],
    "local thread state must win over remote copies during initial hydration",
  );
  assert.equal(
    mergedThreads.find((thread) => thread.thread_key === "silkroute:returns")?.chat_mode,
    "explain",
    "hydration must preserve per-thread chat mode for existing local threads",
  );

  const initialIndex = indexChatThreadSnapshots(mergedThreads);
  const noChangeDiff = diffChatThreadSnapshots(initialIndex, indexChatThreadSnapshots(mergedThreads));
  assert.deepEqual(
    noChangeDiff,
    { dirtyKeys: [], deletedKeys: [] },
    "repeating hydration must not create synthetic dirty state after the first hydrate pass",
  );

  const changedThreads = [
    makeThread({
      thread_key: "silkroute:sales",
      turns: [{ role: "user", message: "Break this down by store" }],
      chat_mode: "chart",
    }),
    {
      ...localThreads.find((thread) => thread.thread_key === "silkroute:returns")!,
    },
  ];
  const changedDiff = diffChatThreadSnapshots(initialIndex, indexChatThreadSnapshots(changedThreads));
  assert.deepEqual(changedDiff.dirtyKeys, ["silkroute:sales"], "only changed threads should be marked dirty");
  assert.deepEqual(changedDiff.deletedKeys, ["silkroute:inventory"], "removed threads should be tracked separately");

  const cacheSeed = [
    {
      id: 1,
      thread_key: "silkroute:sales",
      turns: [{ role: "user", message: "Show sales" }],
      chat_state: null,
      last_chart_spec: null,
      saved_prompts: [],
      chat_mode: "chart",
      updated_at: "2026-04-10T00:00:00Z",
    },
  ];
  const cacheAfterUpsert = upsertChatThreadCache(cacheSeed, {
    ...cacheSeed[0],
    id: 2,
    turns: [{ role: "user", message: "Show sales by region" }],
    updated_at: "2026-04-10T00:05:00Z",
  });
  assert.equal(cacheAfterUpsert.length, 1, "upsert cache updates must replace in-place, not duplicate threads");
  assert.equal(cacheAfterUpsert[0]?.id, 2, "upsert cache updates must keep the newest server payload");
  const cacheAfterSecondUpsert = upsertChatThreadCache(cacheAfterUpsert, {
    ...cacheAfterUpsert[0],
    id: 3,
    chat_mode: "explain",
    updated_at: "2026-04-10T00:10:00Z",
  });
  assert.equal(cacheAfterSecondUpsert.length, 1, "repeated upserts must not create refetch-storm duplicates in cache");
  assert.equal(cacheAfterSecondUpsert[0]?.chat_mode, "explain", "cache updates must keep the latest thread mode");

  const cacheAfterDelete = deleteChatThreadCache(cacheAfterSecondUpsert, "silkroute:sales");
  assert.deepEqual(cacheAfterDelete, [], "delete cache updates must remove only the deleted thread");

  console.log("chat_sync_smoke: ok");
}

run();
