import { useMemo, useState } from "react";
import { KpiCard, Page } from "../components/AppLayout";
import type { SentimentLabel, Snapshot, SourceName, SourceStatus } from "../types";

export type DashboardSource = "summary" | SourceName;

const sourceLabels: Record<DashboardSource, string> = {
  summary: "Ringkasan",
  tiktok: "TikTok",
  instagram: "Instagram",
  facebook: "Facebook",
  maps: "Google Maps",
  shopee: "Shopee",
  youtube: "YouTube"
};

const sourceStatuses: Record<SourceStatus, string> = {
  disabled: "Nonaktif",
  misconfigured: "Belum dikonfigurasi",
  queued: "Menunggu",
  running: "Berjalan",
  fresh: "Terbaru",
  empty: "Tidak ada hasil",
  stale: "Snapshot lama",
  budget_exhausted: "Budget habis",
  error: "Gagal"
};

function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function statusMessage(status: SourceStatus, message: string | null) {
  if (message) return message;
  const messages: Partial<Record<SourceStatus, string>> = {
    misconfigured: "Provider belum dikonfigurasi. Snapshot tersimpan tetap tersedia.",
    empty: "Provider berhasil dijalankan, tetapi tidak menemukan evidence relevan.",
    budget_exhausted: "Budget provider sudah tercapai. Data tersimpan tidak dihapus.",
    error: "Provider gagal. Evidence dari snapshot sebelumnya tetap dipertahankan."
  };
  return messages[status] ?? "Belum ada evidence tersimpan dari sumber ini.";
}

function displayStatus(status: SourceStatus, lastFinishedAt: string | null) {
  return !lastFinishedAt && ["empty", "stale", "fresh"].includes(status)
    ? "Belum pernah dijalankan"
    : sourceStatuses[status];
}

export function DashboardScreen({
  snapshot,
  source,
  onAddTopic
}: {
  snapshot: Snapshot | null;
  source: DashboardSource;
  onAddTopic: () => void;
}) {
  const [query, setQuery] = useState("");
  const evidence = useMemo(() => {
    if (!snapshot) return [];
    return (snapshot.evidence ?? []).filter((item) => source === "summary" || item.source === source);
  }, [snapshot, source]);
  const sourceSummary = snapshot?.sources?.find((item) => item.source === source);
  const sentiment = snapshot?.sentiment ?? { positif: 0, negatif: 0, netral: 0, pending: 0 };
  const filteredEvidence = evidence.filter((item) =>
    `${item.title ?? ""} ${item.text ?? ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())
  );

  if (!snapshot) {
    return <Page><div className="empty-state neo-box"><span className="material-symbols-outlined">database</span><h2>Snapshot belum tersedia</h2><p>Pilih produk yang dipantau atau tambahkan topik baru untuk mulai menggunakan dashboard.</p><button className="neo-btn primary-btn" onClick={onAddTopic}>＋ Tambah Pemantauan</button></div></Page>;
  }

  return <Page>
    <section className="hero neo-lg">
      <div className="hero-top"><span className="black-label">[MARKET INTELLIGENCE // SNAPSHOT TERSIMPAN]</span><span className="green-label">DIPERBARUI: {formatDate(snapshot.generated_at)}</span></div>
      <h2>{source === "summary" ? <>Pasar sedang <mark>RAMAI</mark> membicarakan {snapshot.topic.name}.</> : <>Evidence <mark>{sourceLabels[source]}</mark> untuk {snapshot.topic.name}.</>}</h2>
      <p>Snapshot tersimpan ditampilkan lebih dahulu. Refresh sumber berjalan terpisah dan tidak mengosongkan evidence yang sudah tersedia.</p>
    </section>
    <section className="kpi-grid">
      <KpiCard label="[TOTAL EVIDENCE]" value={source === "summary" ? snapshot.evidence.length : evidence.length} detail="Evidence relevan tersimpan" />
      <KpiCard label="[SENTIMEN POSITIF]" value={sentiment.positif} detail="Hasil analisis positif" tone="green-card" />
      <KpiCard label="[SENTIMEN NEGATIF]" value={sentiment.negatif} detail="Perlu perhatian operator" tone="red-card" />
      <KpiCard label="[NETRAL / PENDING]" value={sentiment.netral + sentiment.pending} detail="Menunggu atau tanpa opini" tone="yellow-card" />
    </section>
    {source !== "summary" && sourceSummary && <div className={`source-notice status-${sourceSummary.status}`}><strong>{displayStatus(sourceSummary.status, sourceSummary.last_finished_at)}</strong><span>{statusMessage(sourceSummary.status, sourceSummary.message)}</span></div>}
    <section className="source-overview neo-box">
      <div className="panel-header"><h3>{source === "summary" ? "Status seluruh sumber" : `Evidence ${sourceLabels[source]}`}</h3><input aria-label="Cari evidence" placeholder="Cari evidence..." value={query} onChange={(event) => setQuery(event.target.value)} /></div>
      {source === "summary" ? <div className="source-status-grid">{(snapshot.sources ?? []).map((item) => <div className="source-status-card" key={item.source}><span className={`status-dot status-dot-${item.status}`} /><b>{sourceLabels[item.source]}</b><strong>{item.evidence_count}</strong><small>{displayStatus(item.status, item.last_finished_at)}</small></div>)}</div> : <EvidenceList evidence={filteredEvidence} />}
    </section>
    {source === "summary" && <section className="source-overview neo-box evidence-summary"><div className="panel-header"><h3>Evidence terbaru</h3></div><EvidenceList evidence={filteredEvidence.slice(0, 6)} /></section>}
  </Page>;
}

function EvidenceList({ evidence }: { evidence: Snapshot["evidence"] }) {
  if (!evidence.length) return <div className="sub-empty">Belum ada evidence yang cocok dengan filter ini.</div>;
  return <div className="evidence-list">{evidence.map((item) => <article className="evidence-item" key={item.id}><div className="evidence-source">{item.source.toUpperCase()}</div><div className="evidence-content"><div className="evidence-meta"><b>{item.title ?? "Tanpa judul"}</b><span>{formatDate(item.published_at ?? item.collected_at)}</span></div><p>{item.text ?? "Tidak ada teks evidence."}</p><div className="evidence-footer"><span>{analysisLabel(item.analysis?.label)}{item.analysis?.confidence == null ? "" : ` · confidence ${Math.round(item.analysis.confidence * 100)}%`}</span><span>{metricsLabel(item.metrics)}</span><a href={item.url} target="_blank" rel="noopener noreferrer">Buka sumber ↗</a></div></div></article>)}</div>;
}

function analysisLabel(label: SentimentLabel | undefined) {
  return label ? label.toUpperCase() : "PENDING";
}

function metricsLabel(metrics: Snapshot["evidence"][number]["metrics"]) {
  const values = [["views", metrics.views], ["likes", metrics.likes], ["comments", metrics.comments]].filter(([, value]) => value != null).map(([name, value]) => `${name}: ${value}`);
  return values.length ? values.join(" · ") : "Metrik: —";
}
