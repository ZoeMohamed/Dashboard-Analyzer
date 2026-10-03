import { useEffect, useMemo, useState } from "react";
import { dashboardApi } from "./lib/api";
import type { Snapshot, SourceName, SourceStatus, Topic } from "./types";

const sources: Array<{ id: SourceName; label: string; icon: string }> = [
  { id: "summary", label: "Ringkasan", icon: "◈" },
  { id: "tiktok", label: "TikTok", icon: "♪" },
  { id: "instagram", label: "Instagram", icon: "◎" },
  { id: "facebook", label: "Facebook", icon: "f" },
  { id: "maps", label: "Google Maps", icon: "⌖" },
  { id: "shopee", label: "Shopee", icon: "▣" },
  { id: "youtube", label: "YouTube", icon: "▶" }
];

const emptySnapshot = (topic: Topic): Snapshot => ({
  topic,
  total_evidence: 0,
  positive_count: 0,
  negative_count: 0,
  neutral_count: 0,
  pending_count: 0,
  top_aspects: [],
  updated_at: null,
  source_summaries: sources
    .filter((source) => source.id !== "summary")
    .map((source) => ({
      source: source.id as Exclude<SourceName, "summary">,
      evidence_count: 0,
      status: "misconfigured",
      updated_at: null,
      message: "Belum terhubung ke API."
    }))
});

function statusLabel(status: SourceStatus) {
  return {
    disabled: "Nonaktif",
    misconfigured: "Belum dikonfigurasi",
    queued: "Menunggu",
    running: "Berjalan",
    fresh: "Terbaru",
    empty: "Tidak ada hasil",
    stale: "Perlu diperbarui",
    error: "Gagal"
  }[status];
}

function formatDate(value: string | null) {
  if (!value) return "Belum ada snapshot";
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function App() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState("");
  const [selectedSource, setSelectedSource] = useState<SourceName>("summary");
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedTopic = useMemo(
    () => topics.find((topic) => topic.id === selectedTopicId),
    [selectedTopicId, topics]
  );

  useEffect(() => {
    dashboardApi
      .listTopics()
      .then(({ topics: availableTopics }) => {
        setTopics(availableTopics);
        if (availableTopics[0]) setSelectedTopicId(availableTopics[0].id);
      })
      .catch((cause: Error) => setError(cause.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedTopic) {
      setSnapshot(null);
      return;
    }
    setError(null);
    dashboardApi
      .getSnapshot(selectedTopic.id)
      .then(setSnapshot)
      .catch((cause: Error) => {
        setSnapshot(emptySnapshot(selectedTopic));
        setError(cause.message);
      });
  }, [selectedTopic]);

  const currentSnapshot = snapshot ?? (selectedTopic ? emptySnapshot(selectedTopic) : null);
  const currentSource = currentSnapshot?.source_summaries.find(
    (item) => item.source === selectedSource
  );

  async function handleRefresh() {
    if (!selectedTopic) return;
    setRefreshing(true);
    setError(null);
    try {
      await dashboardApi.refresh(selectedTopic.id);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">DA</div>
          <div>
            <strong>Dashboard</strong>
            <span>Analyzer</span>
          </div>
        </div>

        <div className="sidebar-section-label">Sumber data</div>
        <nav className="source-nav" aria-label="Sumber data">
          {sources.map((source) => {
            const summary = currentSnapshot?.source_summaries.find(
              (item) => item.source === source.id
            );
            return (
              <button
                className={`source-link ${selectedSource === source.id ? "active" : ""}`}
                key={source.id}
                onClick={() => setSelectedSource(source.id)}
              >
                <span className="source-icon">{source.icon}</span>
                <span className="source-name">{source.label}</span>
                {source.id !== "summary" && (
                  <span className="source-count">{summary?.evidence_count ?? 0}</span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <span className="connection-dot" />
          <span>{error ? "API tidak tersambung" : "Sistem siap digunakan"}</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace / <strong>Analisis produk</strong></div>
          <div className="topbar-actions">
            <span className="last-sync">Snapshot: {formatDate(currentSnapshot?.updated_at ?? null)}</span>
            <button className="button button-primary" disabled={!selectedTopic || refreshing} onClick={handleRefresh}>
              <span>{refreshing ? "↻" : "↗"}</span>
              {refreshing ? "Memperbarui..." : "Refresh sumber"}
            </button>
          </div>
        </header>

        <section className="page-heading">
          <div>
            <p className="eyebrow">Pemantauan produk UMKM</p>
            <h1>{selectedTopic?.name ?? "Mulai pantau produk"}</h1>
            <p className="muted">
              {selectedTopic
                ? `Keyword aktif: ${selectedTopic.keywords.join(", ")}`
                : "Tambahkan produk untuk mulai mengumpulkan evidence publik."}
            </p>
          </div>
          <button className="button button-secondary" disabled>
            + Pantau produk
          </button>
        </section>

        {error && (
          <div className="notice notice-error" role="alert">
            <strong>Koneksi API belum tersedia.</strong>
            <span>{error} Jalankan backend FastAPI untuk memuat data live.</span>
          </div>
        )}

        {loading ? (
          <div className="loading-panel">Memuat daftar produk...</div>
        ) : !currentSnapshot ? (
          <div className="empty-panel">
            <div className="empty-icon">⌁</div>
            <h2>Belum ada produk yang dipantau</h2>
            <p>Produk baru dan konfigurasi sumber akan tersedia setelah endpoint topics aktif.</p>
          </div>
        ) : (
          <>
            <section className="metric-grid" aria-label="Ringkasan metrik">
              <MetricCard label="Total evidence" value={currentSnapshot.total_evidence} tone="blue" />
              <MetricCard label="Sentimen positif" value={currentSnapshot.positive_count} tone="green" />
              <MetricCard label="Sentimen negatif" value={currentSnapshot.negative_count} tone="red" />
              <MetricCard label="Netral / pending" value={currentSnapshot.neutral_count + currentSnapshot.pending_count} tone="amber" />
            </section>

            <section className="content-grid">
              <div className="panel overview-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Distribusi sumber</p>
                    <h2>Status pengumpulan</h2>
                  </div>
                  <span className="panel-date">{formatDate(currentSnapshot.updated_at)}</span>
                </div>
                <div className="source-status-list">
                  {currentSnapshot.source_summaries.map((item) => (
                    <button className="status-row" key={item.source} onClick={() => setSelectedSource(item.source)}>
                      <span className={`status-bullet status-${item.status}`} />
                      <span className="status-source">{sources.find((source) => source.id === item.source)?.label}</span>
                      <span className="status-number">{item.evidence_count}</span>
                      <span className={`status-pill status-pill-${item.status}`}>{statusLabel(item.status)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="panel aspects-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Insight</p>
                    <h2>Aspek yang sering disebut</h2>
                  </div>
                </div>
                {currentSnapshot.top_aspects.length ? (
                  <div className="aspect-list">
                    {currentSnapshot.top_aspects.map((aspect) => <span className="aspect-tag" key={aspect}>{aspect}</span>)}
                  </div>
                ) : (
                  <div className="subtle-empty">Aspek akan muncul setelah evidence dianalisis.</div>
                )}
              </div>
            </section>

            <section className="panel detail-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Detail sumber</p>
                  <h2>{selectedSource === "summary" ? "Ringkasan evidence" : sources.find((source) => source.id === selectedSource)?.label}</h2>
                </div>
                {currentSource && <span className={`status-pill status-pill-${currentSource.status}`}>{statusLabel(currentSource.status)}</span>}
              </div>
              <div className="detail-empty">
                <div className="detail-empty-icon">{selectedSource === "summary" ? "◈" : sources.find((source) => source.id === selectedSource)?.icon}</div>
                <h3>{currentSource ? statusLabel(currentSource.status) : "Belum ada evidence"}</h3>
                <p>{currentSource?.message ?? "Evidence tersimpan dari sumber ini akan tampil di sini setelah refresh berhasil."}</p>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function MetricCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="metric-card">
      <span className={`metric-icon metric-${tone}`}>●</span>
      <div>
        <span className="metric-label">{label}</span>
        <strong>{value.toLocaleString("id-ID")}</strong>
      </div>
    </div>
  );
}

export default App;
