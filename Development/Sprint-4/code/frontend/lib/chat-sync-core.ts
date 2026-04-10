export interface ChatThreadSnapshot {
  thread_key: string;
  turns: ReadonlyArray<unknown>;
  chat_state: Record<string, unknown> | null;
  last_chart_spec: Record<string, unknown> | null;
  saved_prompts: string[];
  chat_mode: string;
}

export interface BuildChatThreadSnapshotsInput {
  chatTurnsByKey: Record<string, ReadonlyArray<unknown>>;
  chatStateByKey: Record<string, unknown>;
  lastChartSpecByKey: Record<string, unknown>;
  savedPromptsByKey: Record<string, string[] | undefined>;
  chatMode: string;
}

export interface ChatThreadDiff {
  dirtyKeys: string[];
  deletedKeys: string[];
}

type ChatThreadIndex = Record<string, ChatThreadSnapshot>;

function stableSerialize(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableSerialize(item)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

function serializeChatThread(thread: ChatThreadSnapshot): string {
  return stableSerialize({
    thread_key: thread.thread_key,
    turns: thread.turns,
    chat_state: thread.chat_state,
    last_chart_spec: thread.last_chart_spec,
    saved_prompts: thread.saved_prompts,
    chat_mode: thread.chat_mode,
  });
}

export function shouldEnableChatSync(enabled: boolean): boolean {
  return enabled;
}

export function buildChatThreadSnapshots(input: BuildChatThreadSnapshotsInput): ChatThreadSnapshot[] {
  return Object.keys(input.chatTurnsByKey)
    .sort((left, right) => left.localeCompare(right))
    .flatMap((threadKey) => {
      const turns = input.chatTurnsByKey[threadKey];
      if (!Array.isArray(turns) || turns.length === 0) {
        return [];
      }
      return [
        {
          thread_key: threadKey,
          turns: [...turns],
          chat_state: (input.chatStateByKey[threadKey] as Record<string, unknown> | null | undefined) ?? null,
          last_chart_spec: (input.lastChartSpecByKey[threadKey] as Record<string, unknown> | null | undefined) ?? null,
          saved_prompts: [...(input.savedPromptsByKey[threadKey] ?? [])],
          chat_mode: input.chatMode,
        },
      ];
    });
}

export function indexChatThreadSnapshots(threads: ReadonlyArray<ChatThreadSnapshot>): ChatThreadIndex {
  return Object.fromEntries(threads.map((thread) => [thread.thread_key, thread]));
}

export function diffChatThreadSnapshots(
  previous: ChatThreadIndex,
  current: ChatThreadIndex,
): ChatThreadDiff {
  const dirtyKeys: string[] = [];
  const deletedKeys: string[] = [];

  for (const [threadKey, currentThread] of Object.entries(current)) {
    const previousThread = previous[threadKey];
    if (!previousThread || serializeChatThread(previousThread) !== serializeChatThread(currentThread)) {
      dirtyKeys.push(threadKey);
    }
  }

  for (const threadKey of Object.keys(previous)) {
    if (!(threadKey in current)) {
      deletedKeys.push(threadKey);
    }
  }

  return { dirtyKeys, deletedKeys };
}

export function mergeHydratedChatThreads(params: {
  localThreads: ReadonlyArray<ChatThreadSnapshot>;
  remoteThreads: ReadonlyArray<ChatThreadSnapshot>;
}): ChatThreadSnapshot[] {
  const localByKey = indexChatThreadSnapshots(params.localThreads);
  const remoteOnlyThreads = params.remoteThreads.filter((thread) => !(thread.thread_key in localByKey));
  return [...remoteOnlyThreads, ...params.localThreads];
}

export function upsertChatThreadCache<T extends { thread_key: string }>(
  currentThreads: ReadonlyArray<T> | undefined,
  nextThread: T,
): T[] {
  const withoutExisting = (currentThreads ?? []).filter((thread) => thread.thread_key !== nextThread.thread_key);
  return [nextThread, ...withoutExisting];
}

export function deleteChatThreadCache<T extends { thread_key: string }>(
  currentThreads: ReadonlyArray<T> | undefined,
  threadKey: string,
): T[] {
  return (currentThreads ?? []).filter((thread) => thread.thread_key !== threadKey);
}
