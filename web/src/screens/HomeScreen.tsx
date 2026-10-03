import { useState } from "react";
import { Hero, KpiCard, Page } from "../components/AppLayout";

export function HomeScreen() {
  const [product, setProduct] = useState("Keripik Tempe Crispy Daun Jeruk");
  const [submitted, setSubmitted] = useState(false);
  return <Page>
    <Hero eyebrow="[MARKET INTELLIGENCE UMKM // SEMARANG PIPELINE LIVE]" title={<>Pasar sedang <mark>RAMAI</mark> membicarakan produkmu.</>}>
      Pantau sinyal real-time dari media sosial TikTok/IG, ulasan Google Maps cabang, tren konten YouTube kuliner, dan pergerakan harga kompetitor Shopee dalam satu pusat komando intelijen UMKM.
    </Hero>
    <div className="hero-meta"><span>Fokus Pantauan: <b>Sambal Bawang Bu Krisna</b> · Kategori: <b>Kuliner Siap Saji & Oleh-Oleh</b></span><strong className="negative">⚠ KONSENSUS: PERLU TINDAKAN PENGEMASAN (URGENT)</strong></div>
    <section className="kpi-grid">
      <KpiCard label="[PRODUK DIPANTAU]" value="12 Produk" detail="Dipantau otomatis 24/7 di 4 kanal" />
      <KpiCard label="[SINYAL PASAR]" value="248 Sinyal" detail="▲ +34% vs pekan lalu" />
      <KpiCard label="[SENTIMEN PUBLIK]" value="+68% Positif" detail="22% Netral · 10% Negatif" tone="green-card" />
      <KpiCard label="[SUMBER AKTIF]" value="4 Saluran" detail="TikTok, IG, Maps, Shopee aktif" tone="yellow-card" />
    </section>
    <section className="section-block">
      <div className="section-title"><h3>Radar Prioritas / Alert Sinyal</h3><span className="black-label">UPDATE: 12 MENIT LALU</span></div>
      <div className="alert-grid">
        <article className="alert-card neo-box red-accent"><span className="alert-tag">URGENT // NEGATIF</span><h4>Botol bocor saat pengiriman</h4><p>12 keluhan serupa terdeteksi dari komentar TikTok dan ulasan Shopee.</p><b>→ Prioritas: Audit seal aluminium</b></article>
        <article className="alert-card neo-box green-accent"><span className="alert-tag">OPPORTUNITY // POSITIF</span><h4>Video kuliner masuk FYP</h4><p>Konversi 64 order Shopee dalam 6 jam setelah video @kulineran_semarang.</p><b>→ Rekomendasi: Repost ke IG Story</b></article>
        <article className="alert-card neo-box"><span className="alert-tag">SIGNAL // TREN</span><h4>Varian cumi ditanyakan</h4><p>Permintaan PO varian cumi korek naik 28% dari pembeli Banyumanik.</p><b>→ Validasi stok outlet</b></article>
      </div>
    </section>
    <section className="section-block" id="tambah-pemantauan">
      <div className="section-title"><div><span className="black-label">FORMULIR MODUL 06</span><h3>TAMBAH PEMANTAUAN BARU</h3></div><span className="green-label">SLOT TERSEDIA: 4 / 20 PRODUK</span></div>
      {submitted && <div className="success-box">✓ Produk “{product}” berhasil didaftarkan ke crawler pipeline AI!</div>}
      <form className="monitor-form neo-lg" onSubmit={(event) => { event.preventDefault(); setSubmitted(true); }}>
        <label>[CARI] &gt;_ 01. Nama Produk UMKM<input value={product} onChange={(event) => setProduct(event.target.value)} /></label>
        <label>[LOKASI] &gt;_ 02. Kota Target Pantau<select><option>Semarang (Jawa Tengah)</option><option>Solo / Surakarta</option><option>Yogyakarta (DIY)</option></select></label>
        <label>[SEKTOR] &gt;_ 03. Kategori UMKM<select><option>Camilan & Makanan Ringan</option><option>Kuliner Siap Saji / Warung</option></select></label>
        <div className="keyword-box"><b>⚡ Generator Kata Kunci Otomatis (Pipeline AI)</b><button type="button" className="neo-btn" onClick={() => window.alert("Kata kunci telah disegarkan!")}>[Segarkan Kata Kunci]</button><div><span>#keripiktempesemarang</span><span>tempe crispy daun jeruk enak</span><span>oleh oleh khas semarang</span></div></div>
        <div className="form-actions"><label className="check"><input type="checkbox" defaultChecked /> Sinkronisasi otomatis ke Shopee Scraper, Maps & YouTube Monitor</label><button className="neo-btn primary-btn">MULAI PANTAU PRODUK INI →</button></div>
      </form>
    </section>
  </Page>;
}
