import { useState } from "react";
import { Hero, KpiCard, Page } from "../components/AppLayout";

const feed = [
  ["TT", "@dinda_foodies", "NEGATIF (-0.86)", "Packing Ekspedisi", "Enak banget sambalnya, TAPI tolong dong seller perbaiki seal tutup botolnya... pas nyampe Jakarta minyaknya udah tumpah blepotan.", "neg"],
  ["TT", "@kulineran_semarang", "POSITIF (+0.92)", "Rasa & Porsi Bawang", "Gila sih sambal bawang Bu Krisna ini gak pelit minyak dan potongan bawang merahnya! Udah repurchase 3x.", "pos"],
  ["IG", "@mas_budi_semarang", "PERTANYAAN (0.00)", "Info Cabang & Varian Cumi", "Mau tanya kalau cabang Banyumanik buka sampai jam berapa? Sambal cumi koreknya ready atau PO?", "neutral"],
  ["IG", "@jajanankotatua", "POSITIF (+0.88)", "Oleh-oleh Khas", "Beli 5 botol buat oleh-oleh kantor Jakarta. Rasanya konsisten pedas gurih, paling legit di Semarang.", "pos"]
];

export function SuaraPasarScreen() {
  const [filter, setFilter] = useState("all");
  const items = feed.filter((item) => filter === "all" || (filter === "urgent" ? item[5] === "neg" : item[5] === filter));
  return <Page>
    <Hero eyebrow="[MODUL 02 // SUARA PASAR & SENTIMEN KONSUMEN]" title={<>Apa kata mereka tentang <mark>Sambal Bawang Bu Krisna?</mark></>}>
      Analisis NLP & sentimen percakapan organik dari video, ulasan, dan komentar TikTok & Instagram secara real-time. Membaca suara pasar tanpa filter sebelum mengambil keputusan.
      <button className="neo-btn primary-btn hero-action" onClick={() => window.alert("Mengunduh laporan PDF analisis sentimen mingguan...")}>↓ Export Laporan PDF</button>
    </Hero>
    <section className="kpi-grid"><KpiCard label="SINYAL TERTANGKAP" value="1.428" detail="+34% vs pekan lalu" /><KpiCard label="SENTIMEN POSITIF NETTO" value="+68.2%" detail="974 mention positif" tone="green-card" /><KpiCard label="TOPIK DOMINAN" value="Packing" detail="34% percakapan" /><KpiCard label="PERLU RESPONS" value="12" detail="Komplain belum dibalas" tone="red-card" /></section>
    <section className="feed-panel neo-box"><div className="panel-header"><h3>Feed Percakapan Terbaru</h3><div className="filter-tabs">{[["all", "Semua (1.428)"], ["urgent", "Urgent (12)"], ["pos", "Positif"], ["neutral", "Pertanyaan"]].map(([key, label]) => <button key={key} className={filter === key ? "selected" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div></div>{items.map((item) => <article className={`feed-item ${item[5]}`} key={item[1]}><div className="feed-source">{item[0]}<small>{item[1]}</small></div><div className="feed-body"><div className="feed-meta"><b>{item[3]}</b><span className={`sentiment ${item[5]}`}>{item[2]}</span></div><p>“{item[4]}”</p><small>Video utama · 2 jam lalu</small></div><button className="more-button">···</button></article>)}</section>
  </Page>;
}
