import type { ReactNode } from "react";
import type { DashboardSource } from "../screens/DashboardScreen";
import type { Topic } from "../types";

const navItems: Array<{ source: DashboardSource; label: string; icon: string }> = [
  { source: "summary", label: "Ringkasan", icon: "dashboard" },
  { source: "tiktok", label: "TikTok", icon: "music_note" },
  { source: "instagram", label: "Instagram", icon: "photo_camera" },
  { source: "facebook", label: "Facebook", icon: "thumb_up" },
  { source: "maps", label: "Google Maps", icon: "pin_drop" },
  { source: "shopee", label: "Shopee", icon: "shopping_bag" },
  { source: "youtube", label: "YouTube", icon: "smart_display" }
];

export function AppLayout({
  source,
  topic,
  topics,
  onSelectTopic,
  onAddTopic,
  onRefresh,
  refreshing,
  error,
  children
}: {
  source: DashboardSource;
  topic?: Topic;
  topics: Topic[];
  onSelectTopic: (id: string) => void;
  onAddTopic: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  error: string | null;
  children: ReactNode;
}) {
  return <div className="app-frame">
    <aside className="side-nav">
      <div className="side-content">
        <div className="brand-card neo-sm"><div className="brand-row"><div className="brand-mark">DA</div><div><h1>DASHBOARD ANALYZER</h1><span>Intelijen Pasar UMKM</span></div></div><p>Evidence publik // sebelum keputusan</p></div>
        <div className="watch-card"><div className="watch-label"><span>Produk Dipantau:</span><i /></div><select aria-label="Pilih produk" value={topic?.id ?? ""} onChange={(event) => onSelectTopic(event.target.value)}><option value="" disabled>Pilih produk</option>{topics.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select><small>{topic?.cities?.join(" · ") ?? "Belum ada lokasi"}</small></div>
        <nav className="main-nav" aria-label="Sumber evidence">{navItems.map((item) => <button key={item.source} className={`nav-item ${source === item.source ? "active" : ""}`} onClick={() => { window.location.hash = item.source === "summary" ? "/" : `/${item.source}`; }}><span className="material-symbols-outlined">{item.icon}</span><span>{item.label}</span></button>)}<button className="add-watch" onClick={onAddTopic}><span className="material-symbols-outlined">add_circle</span><span>Pantau produk</span></button></nav>
      </div>
      <div className="telemetry"><strong><span className="material-symbols-outlined">verified</span> API backend</strong><div><span className={`pulse-dot ${error ? "offline-dot" : ""}`} /> {error ? "Perlu perhatian" : "Snapshot tersedia"} <b>{error ? "ERROR" : "READY"}</b></div><small>Credential provider tidak pernah dikirim ke browser</small></div>
    </aside>
    <div className="page-area">
      <header className="top-nav"><div className="crumb"><span className="top-badge">DASHBOARD ANALYZER</span><span>{topic?.name ?? "Belum memilih produk"}</span><em>/</em><strong>{navItems.find((item) => item.source === source)?.label}</strong></div><div className="top-actions"><span className="connected"><i /> {refreshing ? "Refresh berjalan" : "Snapshot tersimpan"}</span><button className="neo-btn refresh-btn" disabled={!topic || refreshing} onClick={onRefresh}>↻ <span>{refreshing ? "Memperbarui..." : "Refresh sumber"}</span></button></div></header>
      {children}
    </div>
  </div>;
}

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) { return <main className={`page-content ${className}`}>{children}</main>; }
export function KpiCard({ label, value, detail, tone = "" }: { label: string; value: ReactNode; detail: string; tone?: string }) { return <div className={`kpi neo-box ${tone}`}><div className="kpi-label">{label}<span className="material-symbols-outlined">monitoring</span></div><strong>{value}</strong><p>{detail}</p></div>; }
