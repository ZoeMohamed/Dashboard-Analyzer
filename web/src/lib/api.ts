import type { RefreshResponse, Snapshot, TopicListResponse } from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    ...init
  });

  if (!response.ok) {
    throw new Error(`API mengembalikan status ${response.status}.`);
  }

  return response.json() as Promise<T>;
}

export const dashboardApi = {
  listTopics: () => request<TopicListResponse>("/api/topics"),
  getSnapshot: (topicId: string) =>
    request<Snapshot>(`/api/topics/${encodeURIComponent(topicId)}/snapshot`),
  refresh: (topicId: string) =>
    request<RefreshResponse>(`/api/topics/${encodeURIComponent(topicId)}/refresh`, {
      method: "POST"
    })
};
