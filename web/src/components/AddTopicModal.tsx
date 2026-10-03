import { useState, type FormEvent } from "react";
import type { TopicCreate } from "../types";

export function AddTopicModal({
  isOpen,
  onClose,
  onSubmit
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: TopicCreate) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [keywordsRaw, setKeywordsRaw] = useState("");
  const [productTermsRaw, setProductTermsRaw] = useState("");
  const [excludeTermsRaw, setExcludeTermsRaw] = useState("");
  const [citiesRaw, setCitiesRaw] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  function parseCommaList(value: string): string[] {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function addPresetExclude(preset: string) {
    const current = parseCommaList(excludeTermsRaw);
    const presets = parseCommaList(preset);
    const combined = Array.from(new Set([...current, ...presets]));
    setExcludeTermsRaw(combined.join(", "));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const cleanName = name.trim();
    if (!cleanName || cleanName.length < 2) {
      setError("Nama produk wajib diisi (minimal 2 karakter).");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload: TopicCreate = {
        name: cleanName,
        keywords: parseCommaList(keywordsRaw),
        product_terms: parseCommaList(productTermsRaw),
        exclude_terms: parseCommaList(excludeTermsRaw),
        cities: parseCommaList(citiesRaw)
      };
      await onSubmit(payload);
      // Reset form
      setName("");
      setKeywordsRaw("");
      setProductTermsRaw("");
      setExcludeTermsRaw("");
      setCitiesRaw("");
      onClose();
    } catch (cause) {
      setError((cause as Error).message || "Gagal membuat topik pemantauan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-card neo-lg" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <div>
            <span className="black-label">[INTELIJEN PASAR // INPUT PRODUK]</span>
            <h2 id="modal-title">Pantau Produk Baru</h2>
          </div>
          <button className="modal-close-btn" type="button" aria-label="Tutup modal" onClick={onClose}>
            ✕
          </button>
        </header>

        {error && (
          <div className="source-notice status-error" style={{ marginBottom: 16 }}>
            <strong>KESALAHAN:</strong>
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-body">
            <div className="form-group">
              <label htmlFor="topic-name">
                Nama Produk UMKM <span className="red-label" style={{ padding: "2px 5px", fontSize: 9 }}>WAJIB</span>
              </label>
              <input
                id="topic-name"
                type="text"
                autoFocus
                required
                disabled={loading}
                placeholder="misal: Kopi Aren Gula Jawa, Seblak Pedas, Keripik Pisang Lumer"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className="form-hint">Nama produk spesifik yang akan dilacak opini & sentimen publiknya.</p>
            </div>

            <div className="form-group">
              <label htmlFor="topic-keywords">Kata Kunci Pencarian (Opsional)</label>
              <input
                id="topic-keywords"
                type="text"
                disabled={loading}
                placeholder="pisahkan dengan koma, misal: kopi susu, kopi aren, capcin"
                value={keywordsRaw}
                onChange={(e) => setKeywordsRaw(e.target.value)}
              />
              <p className="form-hint">Kata kunci yang digunakan scrapper saat mencari feed di platform publik.</p>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="topic-product-terms">Istilah Terkait / Product Terms</label>
                <input
                  id="topic-product-terms"
                  type="text"
                  disabled={loading}
                  placeholder="misal: kopi, aren, espresso"
                  value={productTermsRaw}
                  onChange={(e) => setProductTermsRaw(e.target.value)}
                />
                <p className="form-hint">Syarat wajib agar teks dinilai relevan dengan produk.</p>
              </div>

              <div className="form-group">
                <label htmlFor="topic-cities">Target Wilayah / Kota</label>
                <input
                  id="topic-cities"
                  type="text"
                  disabled={loading}
                  placeholder="misal: Bandung, Jakarta, Semarang"
                  value={citiesRaw}
                  onChange={(e) => setCitiesRaw(e.target.value)}
                />
                <p className="form-hint">Digunakan saat mencari lokasi & ulasan Google Maps.</p>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="topic-exclude-terms">Filter Kata Sampah / Exclude Terms</label>
              <input
                id="topic-exclude-terms"
                type="text"
                disabled={loading}
                placeholder="misal: upin ipin, kartun, lagu anak, gameplay"
                value={excludeTermsRaw}
                onChange={(e) => setExcludeTermsRaw(e.target.value)}
              />
              <p className="form-hint">Konten yang memuat kata ini akan otomatis ditolak oleh intelligence filter.</p>
              <div className="preset-chips">
                <span className="form-hint" style={{ alignSelf: "center", marginRight: 4 }}>Filter cepat:</span>
                <button
                  type="button"
                  className="preset-chip"
                  onClick={() => addPresetExclude("upin ipin, kartun, lagu anak, animasi, balita")}
                >
                  + Kartun & Anak
                </button>
                <button
                  type="button"
                  className="preset-chip"
                  onClick={() => addPresetExclude("gameplay, gaming, meme, parodi, sketsa")}
                >
                  + Hiburan & Gaming
                </button>
              </div>
            </div>
          </div>

          <footer className="modal-footer">
            <button className="neo-btn" type="button" disabled={loading} onClick={onClose}>
              Batal
            </button>
            <button className="neo-btn primary-btn" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <span className="material-symbols-outlined" style={{ animation: "spin 1s infinite linear" }}>sync</span>
                  Menyimpan...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined">rocket_launch</span>
                  Mulai Pantau Produk
                </>
              )}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
