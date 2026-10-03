import { useState } from "react";
import { KpiCard, Page } from "../components/AppLayout";

const initialSnapshots = [
  ["#SNP-2025-W20", "12 Mei 2025 · 23:59 WIB", "Otomatis Mingguan", "Sentimen melonjak pasca video review viral di TikTok kuliner.", "+68% Positif", "★ 4.8"],
  ["#SNP-2025-W19", "05 Mei 2025 · 23:59 WIB", "Otomatis Mingguan", "Penerapan segel baru aluminium pada kemasan botol kaca.", "+58% Netral", "★ 4.6"],
  ["#SNP-2025-ALERT-01", "22 Apr 2025 · 14:15 WIB", "Insiden Kritis", "Krisis ulasan Shopee: Botol bocor saat kiriman ekspedisi luar kota.", "-42% Negatif", "★ 3.9"]
];
export function SnapshotScreen() {
  const [snapshots, setSnapshots] = useState(initialSnapshots);
  return <Page><section className="hero neo-lg"><div className="hero-top"><span className="yellow-label">[ARSIP INTELIJEN // REKAP HISTORIS PASAR]</span><button className="neo-btn primary-btn" onClick={() => setSnapshots([["#SNP-2025-M" + Math.floor(Math.random() * 90), "Hari ini · Baru saja", "Manual Operator", "Snapshot manual operator: evaluasi batch seal baru.", "+70% Positif", "★ 4.8"], ...snapshots])}>＋ Buat Snapshot Manual</button></div><h2>Rekam Jejak <mark>[SINYAL PASAR]</mark> & Evaluasi Mingguan.</h2><p>Kumpulan snapshot otomatis mingguan dan insiden pasar penting untuk membandingkan sentimen, pergerakan kompetitor Shopee, dan lonjakan tren sebelum mengambil keputusan bisnis.</p></section><section className="kpi-grid"><KpiCard label="[TOTAL SNAPSHOT]" value={snapshots.length + 10} detail="12 Otomatis · 2 Manual" /><KpiCard label="[TREN 30 HARI]" value="+14% MoM" detail="Dari 54% ke 68% Positif" tone="green-card" /><KpiCard label="[ISU DISELESAIKAN]" value="3 Masalah" detail="Termasuk komplain botol bocor" /><KpiCard label="[STATUS PASAR]" value="AMAN" detail="Skor Konsensus: 8.4 / 10" tone="green-card" /></section><section className="snapshot-list neo-box"><div className="table-title">ARSIP SNAPSHOT & INSIDEN PASAR</div>{snapshots.map((snapshot) => <article className="snapshot-row" key={snapshot[0]}><div className="snapshot-id">{snapshot[0]}<small>{snapshot[1]}</small></div><div><b>{snapshot[2]}</b><p>{snapshot[3]}</p></div><strong className={snapshot[4].includes("-") ? "negative" : "positive"}>{snapshot[4]}</strong><span>{snapshot[5]}</span><button className="neo-btn">Lihat Detail</button></article>)}</section></Page>;
}
