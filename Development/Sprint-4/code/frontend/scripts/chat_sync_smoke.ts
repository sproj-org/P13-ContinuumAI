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
    },
    chatStateByKey: {
      "silkroute:sales": { clarify_id: null, selections: {}, original_user_intent: "Show sales by region" },
    },
    lastChartSpecByKey: {
      "silkroute:sales": { mark: "bar" },
    },
    savedPromptsByKey: {
      "silkroute:sales": ["Show sales by region"],
    },
    chatMode: "chart",
  });

  const remoteThreads = [
    makeThread({
      thread_key: "silkroute:sales",
      turns: [{ role: "user", message: "Older remote copy" }],
      chat_mode: "auto",
    }),
    makeThread({
      thread_key: "silkroute:returns",
      turns: [{ role: "user", message: "Show returns" }],
      chat_mode: "chart",
    }),
  ];

  const mergedThreads = mergeHydratedChatThreads({
    localThreads,
    remoteThreads,
  });
  assert.equal(mergedThreads.length, 2, "hydration should preserve remote-only threads");
  assert.equal(
    mergedThreads.find((thread) => thread.thread_key === "silkroute:sales")?.turns[0],
    localThreads[0]?.turns[0],
    "local thread state must win over remote copies during initial hydration",
  );

  const initialIndex = indexChatThreadSnapshots(mergedThreads);
  const noChangeDiff = diffChatThreadSnapshots(initialIndex, indexChatThreadSnapshots(mergedThreads));
  assert.deepEqual(noChangeDiff, { dirtyKeys: [], deletedKeys: [] }, "repeating hydration must not create synthetic dirty state");

  const changedThreads = [
    makeThread({
      thread_key: "silkroute:sales",
      turns: [{ role: "user", message: "Break this down by store" }],
      chat_mode: "chart",
    }),
  ];
  const changedDiff = diffChatThreadSnapshots(initialIndex, indexChatThreadSnapshots(changedThreads));
  assert.deepEqual(changedDiff.dirtyKeys, ["silkroute:sales"], "only changed threads should be marked dirty");
  assert.deepEqual(changedDiff.deletedKeys, ["silkroute:returns"], "removed threads should be tracked separately");

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

  const cacheAfterDelete = deleteChatThreadCache(cacheAfterUpsert, "silkroute:sales");
  assert.deepEqual(cacheAfterDelete, [], "delete cache updates must remove only the deleted thread");

  console.log("chat_sync_smoke: ok");
}

run();
