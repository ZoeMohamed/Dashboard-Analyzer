export type SourceName =
  | "summary"
  | "tiktok"
  | "instagram"
  | "facebook"
  | "maps"
  | "shopee"
  | "youtube";

export type SourceStatus =
  | "disabled"
  | "misconfigured"
  | "queued"
  | "running"
  | "fresh"
  | "empty"
  | "stale"
  | "error";

export interface Topic {
  id: string;
  name: string;
  keywords: string[];
  created_at: string;
}

export interface SourceSummary {
  source: Exclude<SourceName, "summary">;
  evidence_count: number;
  status: SourceStatus;
  updated_at: string | null;
  message: string | null;
}

export interface Snapshot {
  topic: Topic;
  total_evidence: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  pending_count: number;
  top_aspects: string[];
  source_summaries: SourceSummary[];
  updated_at: string | null;
}

export interface TopicListResponse {
  topics: Topic[];
}

export interface RefreshResponse {
  run_id: string;
  status: SourceStatus;
}
