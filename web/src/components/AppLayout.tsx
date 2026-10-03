import type { ReactNode } from "react";
import type { ScreenPath } from "../App";

const navItems: Array<{ path: ScreenPath; label: string; icon: string; badge: string }> = [
  { path: "/", label: "Beranda", icon: "dashboard", badge: "3 Sinyal" },
  { path: "/suara-pasar", label: "Suara Pasar", icon: "record_voice_over", badge: "TikTok/IG" },
  { path: "/google-maps", label: "Google Maps", icon: "pin_drop", badge: "★ 4.8" },
  { path: "/tren-youtube", label: "Tren YouTube", icon: "smart_display", badge: "Live" },
  { path: "/snapshot", label: "Snapshot", icon: "receipt_long", badge: "Arsip (14)" }
];

function navigate(path: ScreenPath) {
  window.location.hash = path;
}

export function AppLayout({ path, children }: { path: ScreenPath; children: ReactNode }) {
  return (
    <div className="app-frame">
      <aside className="side-nav">
        <div className="side-content">
          <div className="brand-card neo-sm">
            <div className="brand-row">
              <div className="brand-mark">TO</div>
              <div>
                <h1>TREN & OPINI</h1>
                <span>Badan Intelijen UMKM</span>
              </div>
            </div>
            <p>Intelijen UMKM // Data pasar, sebelum keputusan</p>
          </div>

          <div className="watch-card">
            <div className="watch-label"><span>Produk Dipantau:</span><i /></div>
            <strong>Sambal Bawang Bu Krisna</strong>
            <small>Pleburan & Banyumanik · Semarang</small>
          </div>

          <nav className="main-nav">
            {navItems.map((item) => (
              <button key={item.path} className={`nav-item ${path === item.path ? "active" : ""}`} onClick={() => navigate(item.path)}>
                <span className="material-symbols-outlined">{item.icon}</span>
                <span>{item.label}</span>
                <b className={item.path === "/tren-youtube" ? "live-badge" : ""}>{item.badge}</b>
              </button>
            ))}
            <button className="add-watch" onClick={() => navigate("/")}>
              <span className="material-symbols-outlined">add_circle</span> + Tambah Pemantauan
            </button>
          </nav>
        </div>
        <div className="telemetry">
          <strong><span className="material-symbols-outlined">location_on</span> Semarang, Jawa Tengah</strong>
          <div><span className="pulse-dot" /> Pipeline: Live <b>ONLINE</b></div>
          <small>SINKRONISASI: LIVE API v2.4</small>
        </div>
      </aside>

      <div className="page-area">
        <header className="top-nav">
          <div className="crumb"><span className="top-badge">V2.4 INTELIJEN</span><span>Semarang Raya</span><em>/</em><strong>{navItems.find((item) => item.path === path)?.label}</strong></div>
          <div className="top-actions"><span className="connected"><i /> 4 Kanal Terhubung</span><button className="neo-btn refresh-btn" onClick={() => window.alert("Data diperbarui secara realtime dari pipeline scraper!")}>↻ <span>Segarkan Data</span></button></div>
        </header>
        {children}
      </div>
    </div>
  );
}

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <main className={`page-content ${className}`}>{children}</main>;
}

export function Hero({ eyebrow, title, children, action }: { eyebrow: string; title: ReactNode; children: ReactNode; action?: ReactNode }) {
  return <section className="hero neo-lg"><div className="hero-top"><span className="black-label">{eyebrow}</span>{action}</div><h2>{title}</h2><p>{children}</p></section>;
}

export function KpiCard({ label, value, detail, tone = "" }: { label: string; value: ReactNode; detail: string; tone?: string }) {
  return <div className={`kpi neo-box ${tone}`}><div className="kpi-label">{label}<span className="material-symbols-outlined">monitoring</span></div><strong>{value}</strong><p>{detail}</p></div>;
}
