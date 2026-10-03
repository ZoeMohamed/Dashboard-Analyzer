import { useState } from "react";
import { KpiCard, Page } from "../components/AppLayout";

export function GoogleMapsScreen() {
  const [reply, setReply] = useState("Halo Kak Rina, kami mohon maaf atas ketidaknyamanan parkir siang ini. Kami sedang berkoordinasi menambah petugas juru parkir.");
  const [sent, setSent] = useState(false);
  return <Page>
    <div className="control-bar neo-box"><span className="black-label">KONTROL SURVEILANS</span><b>SEMARANG RAYA</b><span className="yellow-label">[3 OUTLET FISIK]</span><button className="neo-btn">↓ Ekspor CSV</button></div>
    <section className="kpi-grid maps-kpi"><KpiCard label="SKOR KONSOLIDASI" value="4.8 / 5.0" detail="★★★★★ EXCELLENT" tone="yellow-card" /><KpiCard label="SENTIMEN POSITIF" value="88.4%" detail="483 ulasan positif" tone="green-card" /><KpiCard label="TINGKAT RESPON" value="94.2%" detail="Waktu respon < 3 jam" /><KpiCard label="TOTAL ULASAN" value="546" detail="Terkumpul di 3 koordinat cabang" /></section>
    <section className="section-block"><h3>Matriks Kinerja Cabang Fisik</h3><div className="branch-grid">{[["Gerai Pleburan (Pusat)", "Jl. Singosari Raya No. 42", "4.8", "342"], ["Outlet Banyumanik", "Jl. Banjarsari Selatan No. 8", "4.7", "128"], ["Kios Oleh-oleh Simpang Lima", "Mall Matahari Lt. 2", "4.9", "76"]].map((branch) => <article className="branch-card neo-box" key={branch[0]}><header><b>⌖ {branch[0]}</b><span className="yellow-label">FLAGSHIP</span></header><p>{branch[1]}</p><div className="branch-stats"><strong>★ {branch[2]} <small>({branch[3]})</small></strong><span>PEAK HOURS<br /><b>11:30 - 13:45</b></span></div><div className="green-note">↑ Sentimen positif dominan</div></article>)}</div></section>
    <section className="maps-review neo-box"><div className="panel-header"><h3>Ulasan yang Perlu Perhatian</h3><span className="red-label">12 KOMPLAIN</span></div><article><div className="review-avatar">R</div><div><b>Rina Pratiwi · ★★☆☆☆</b><small>Gerai Pleburan · 2 hari lalu</small><p>“Sambalnya enak, tapi parkir siang hari sangat penuh dan tidak tertata.”</p><textarea value={reply} onChange={(event) => setReply(event.target.value)} /><button className="neo-btn primary-btn" onClick={() => { setSent(true); setTimeout(() => setSent(false), 2500); }}>{sent ? "✓ Terkirim" : "Kirim Balasan"}</button></div></article></section>
  </Page>;
}
