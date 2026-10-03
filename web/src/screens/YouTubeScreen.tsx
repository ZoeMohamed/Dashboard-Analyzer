import { useState } from "react";
import { KpiCard, Page } from "../components/AppLayout";

const videos = [["Sambal Bawang Bu Krisna: Pedasnya Bikin Keringetan Nampol!", "KulinerSemarangKuy", "Shorts", "128.400", "+34.200/hr"], ["BATTLE 5 SAMBAL BOTOL TERNAMA JATENG! SIAPA JUARANYA?", "Mas Doni Mukbang", "Long-form", "84.100", "+12.100/hr"], ["Hack Nasi Telur Ceplok Pakai Sambal Bu Krisna 🤤", "Dapur Anak Kos Solo", "Shorts", "67.900", "+9.500/hr"]];
export function YouTubeScreen() {
  const [filter, setFilter] = useState("all");
  const visible = videos.filter((video) => filter === "all" || video[2] === filter);
  return <Page className="youtube-page">
    <section className="hero neo-lg"><div className="hero-top"><span className="red-label">[INTELIJEN VIDEO YOUTUBE // PIPELINE V2.4]</span><div className="audience-card"><small>STATUS AUDIENS</small><b>HYPER-ENGAGED</b><span>Ratio Komen 1:18 Views</span></div></div><h2>Perhatian Publik di YouTube Melonjak <mark>[+145%]</mark> Minggu Ini.</h2><p>Analisis video panjang & YouTube Shorts yang mereview dan merekomendasikan kuliner pedas di Jawa Tengah & nasional.</p><div className="filter-tabs"><button className={filter === "all" ? "selected" : ""} onClick={() => setFilter("all")}>Semua (18)</button><button className={filter === "Shorts" ? "selected" : ""} onClick={() => setFilter("Shorts")}>Shorts (12)</button><button className={filter === "Long-form" ? "selected" : ""} onClick={() => setFilter("Long-form")}>Long-form (6)</button></div></section>
    <section className="kpi-grid"><KpiCard label="[INDEKS VIRALITAS]" value="84.2 / 100" detail="Kategori: Sangat Tinggi" /><KpiCard label="[TOTAL VIEWS]" value="482.500" detail="▲ +145% MoM" tone="yellow-card" /><KpiCard label="[SUPPLY VIDEO]" value="18 Video" detail="12 Shorts · 6 Long" /><KpiCard label="[SENTIMEN AUDIENS]" value="91% Positif" detail="2.840 komentar analisis" tone="green-card" /></section>
    <section className="video-table neo-box"><div className="table-title">DIREKTORI VIDEO TERPANTAU</div><div className="table-head"><span>VIDEO & CREATOR</span><span>FORMAT</span><span>VIEWS</span><span>LAJU / JAM</span></div>{visible.map((video) => <article className="video-row" key={video[0]}><div className="video-title"><div className="video-thumb">▶</div><div><b>{video[0]}</b><small>{video[1]} · 42.5K Subs · 1 hari lalu</small></div></div><span className="yellow-label">{video[2]}</span><strong>{video[3]}</strong><span className="positive">{video[4]}</span></article>)}</section>
  </Page>;
}
