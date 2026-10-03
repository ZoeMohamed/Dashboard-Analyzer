import type {
  RefreshResponse,
  Snapshot,
  StreamEvent,
  Topic,
  TopicCreate,
  TopicListResponse
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    let body: { detail?: string; code?: string } = {};
    try {
      body = (await response.json()) as typeof body;
    } catch {
      // The status is still exposed through ApiError when the server has no JSON body.
    }
    throw new ApiError(body.detail ?? `API mengembalikan status ${response.status}.`, response.status, body.code);
  }
  return response.json() as Promise<T>;
}

export const dashboardApi = {
  listTopics: () => request<TopicListResponse>("/api/topics"),
  createTopic: (payload: TopicCreate) =>
    request<Topic>("/api/topics", { method: "POST", body: JSON.stringify(payload) }),
  deleteTopic: (topicId: string) =>
    request<void>(`/api/topics/${encodeURIComponent(topicId)}`, { method: "DELETE" }),
  getSnapshot: (topicId: string) =>
    request<Snapshot>(`/api/topics/${encodeURIComponent(topicId)}/snapshot`),
  refresh: (topicId: string) =>
    request<RefreshResponse>(`/api/topics/${encodeURIComponent(topicId)}/refresh`, { method: "POST" }),
  connectStream(onEvent: (event: StreamEvent) => void, onError: () => void) {
    const stream = new EventSource("/api/stream");
    stream.onmessage = (message) => {
      try {
        onEvent(JSON.parse(message.data) as StreamEvent);
      } catch {
        onError();
      }
    };
    stream.onerror = onError;
    return () => stream.close();
  }
};
