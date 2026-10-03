export type SourceName = "tiktok" | "instagram" | "facebook" | "maps" | "shopee" | "youtube";
export type SourceStatus =
  | "disabled"
  | "misconfigured"
  | "queued"
  | "running"
  | "fresh"
  | "empty"
  | "stale"
  | "budget_exhausted"
  | "error";
export type SentimentLabel = "positif" | "negatif" | "netral" | "pending";

export interface Topic {
  id: string;
  name: string;
  keywords: string[];
  product_terms?: string[];
  exclude_terms?: string[];
  cities?: string[];
  is_active?: boolean;
  created_at: string;
}

export interface EvidenceMetrics {
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
}

export interface Analysis {
  label: SentimentLabel;
  score: number | null;
  confidence: number | null;
  aspects: string[];
  analyzer: string | null;
  analyzed_at?: string | null;
}

export interface Evidence {
  id: string;
  source: SourceName;
  topic_id: string;
  external_id?: string;
  title: string | null;
  text: string | null;
  url: string;
  published_at: string | null;
  collected_at: string;
  relevance_score?: number | null;
  metrics: EvidenceMetrics;
  metadata?: Record<string, unknown>;
  analysis: Analysis | null;
}

export interface SourceSummary {
  source: SourceName;
  status: SourceStatus;
  evidence_count: number;
  last_finished_at: string | null;
  message: string | null;
}

export interface Snapshot {
  topic: Topic;
  generated_at: string;
  sentiment: Record<SentimentLabel, number>;
  sources: SourceSummary[];
  evidence: Evidence[];
}

export interface TopicListResponse {
  topics: Topic[];
}

export interface TopicCreate {
  name: string;
  keywords?: string[];
  product_terms?: string[];
  exclude_terms?: string[];
  cities?: string[];
}

export interface RefreshResponse {
  run_id: string;
  status: SourceStatus;
}

export interface StreamEvent {
  type: "source_status" | "evidence_new" | "analysis_updated" | "error" | "ping";
  topic_id?: string;
  source?: SourceName;
  status?: SourceStatus;
  run_id?: string;
  error_code?: string;
  message?: string;
}
