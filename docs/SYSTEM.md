# System Specification

Dokumen ini adalah sumber kebenaran teknis POC Scrapper. Semua adapter sumber,
repository, intelligence, API, dan UI harus mengikuti kontrak yang sama.

## 1. Tujuan sistem

Pengguna memasukkan nama produk UMKM, misalnya `cappuccino cincau`, `seblak`,
atau `keripik pisang`. Sistem kemudian:

1. Membentuk topik dan kata pencarian terbatas.
2. Mengambil data publik dari provider yang aktif.
3. Menormalkan hasil menjadi `Evidence`.
4. Menolak hasil yang tidak berkaitan dengan produk/UMKM.
5. Menyimpan evidence secara idempotent.
6. Menganalisis sentimen dan aspek yang disebut.
7. Menyajikan snapshot tersimpan melalui API.
8. Menjalankan refresh tanpa membuat dashboard kosong.

## 2. Alur end-to-end

```text
Pengguna membuat Topic
        │
        ▼
Refresh coordinator membuat SourceRun per sumber
        │
        ├── TikTok adapter ──────┐
        ├── Instagram adapter ───┤
        ├── Facebook adapter ────┤
        ├── Maps adapter ────────┼──► Normalisasi Evidence
        ├── Shopee adapter ──────┤
        └── YouTube adapter ─────┘
                                  │
                                  ▼
                     Filter relevansi produk
                                  │
                                  ▼
                     Upsert database + deduplikasi
                                  │
                                  ▼
                   Sentimen dan ekstraksi aspek
                                  │
                                  ▼
                    Snapshot API + progress event
                                  │
                                  ▼
                              Dashboard
```

Provider tidak boleh menulis langsung ke UI. UI tidak boleh memanggil Apify,
Gemini, YouTube, atau database secara langsung.

## 3. Modul dan tanggung jawab

### `app/contracts.py`

Berisi model Pydantic yang menjadi batas antar-modul. File ini dimiliki
integrator. Perubahan membutuhkan contract test dan persetujuan semua pemilik
modul yang terdampak.

### `app/sources/`

Setiap sumber mengimplementasikan interface yang sama:

```python
class SourceAdapter(Protocol):
    name: SourceName

    async def collect(self, topic: Topic, limit: int) -> CollectionResult:
        ...
```

Adapter bertanggung jawab atas request provider, timeout, parsing raw payload,
dan mapping awal. Adapter tidak menentukan sentimen.

### `app/database/`

Repository bertanggung jawab atas persistence, upsert, query snapshot,
transaction, serta pagination. Route API tidak boleh mengandung SQL.

### `app/intelligence/`

Menangani normalisasi Bahasa Indonesia, relevansi produk, sentimen, confidence,
dan ekstraksi aspek. Modul ini tidak melakukan network scraping.

### `app/api/`

Melakukan validasi request, memanggil service, mengubah error domain menjadi
HTTP response, serta menyajikan snapshot/status. Route tidak berisi algoritma
provider atau sentimen.

### `web/`

Mengonsumsi API. Browser hanya menerima data yang aman dan tidak pernah menerima
credential provider/database.

## 4. Kontrak data minimum

Implementasi aktual menggunakan Pydantic. Bentuk berikut adalah kontrak logis
yang wajib dipertahankan.

### Topic

```json
{
  "id": "cappuccino-cincau",
  "name": "Cappuccino Cincau",
  "keywords": ["cappuccino cincau"],
  "product_terms": ["cappuccino", "cincau"],
  "exclude_terms": ["upin ipin", "kartun"],
  "cities": ["Bandung"],
  "is_active": true,
  "created_at": "2026-10-03T00:00:00Z"
}
```

Aturan:

- ID adalah slug stabil dan unik.
- Keyword maksimal lima dan product term maksimal delapan.
- `exclude_terms` digunakan sebelum data disimpan.
- Nama dan array dinormalisasi serta bebas duplikasi case-insensitive.

### Evidence

```json
{
  "id": "instagram:post-123",
  "source": "instagram",
  "topic_id": "cappuccino-cincau",
  "external_id": "post-123",
  "title": "nama akun atau judul",
  "text": "caption, ulasan, atau deskripsi",
  "url": "https://sumber.example/item",
  "published_at": "2026-10-03T00:00:00Z",
  "collected_at": "2026-10-03T00:05:00Z",
  "relevance_score": 0.91,
  "metrics": {
    "views": 1000,
    "likes": 80,
    "comments": 12,
    "shares": 4
  },
  "metadata": {}
}
```

Aturan:

- Primary identity: `(source, topic_id, external_id)`.
- Minimal salah satu dari `title` atau `text` harus terisi.
- `url` harus mengarah ke evidence asli jika provider memberikannya.
- Metrik yang tidak tersedia bernilai `null`, bukan angka buatan.
- Raw payload hanya disimpan jika diperlukan untuk debugging dan dibatasi ukuran.

### SourceRun

```json
{
  "id": "run-id",
  "source": "instagram",
  "topic_id": "cappuccino-cincau",
  "status": "fresh",
  "trigger": "manual",
  "provider_run_id": "optional-provider-id",
  "raw_count": 50,
  "relevant_count": 20,
  "inserted_count": 12,
  "error_code": null,
  "message": null,
  "started_at": "2026-10-03T00:00:00Z",
  "finished_at": "2026-10-03T00:01:00Z"
}
```

Status yang diizinkan:

```text
disabled
misconfigured
queued
running
fresh
empty
stale
budget_exhausted
error
```

`empty` berarti provider berhasil tetapi tidak menemukan evidence relevan.
`misconfigured` berarti credential/configuration belum tersedia. Keduanya bukan
error yang sama.

### Analysis

```json
{
  "evidence_id": "instagram:post-123",
  "label": "positif",
  "score": 0.8,
  "confidence": 0.9,
  "aspects": ["rasa", "kemasan"],
  "analyzer": "gemini",
  "analyzed_at": "2026-10-03T00:01:10Z"
}
```

Label yang diizinkan: `positif`, `negatif`, `netral`, dan `pending`.

## 5. Aturan relevansi produk

Evidence diterima jika:

1. Memuat keyword lengkap; atau
2. Memuat kombinasi product term yang cukup; dan
3. Tidak didominasi exclude term; dan
4. Memiliki konteks produk, pembelian, konsumsi, review, penjual, resep, harga,
   kualitas, permintaan, atau ide usaha.

Evidence ditolak jika hanya cocok secara kebetulan, misalnya judul episode
kartun yang menyebut `ayam goreng` tanpa konteks produk UMKM.

Urutan filter:

```text
normalisasi teks
→ hard exclusion
→ product signal
→ commerce/UMKM context
→ relevance score
→ threshold
```

Filter wajib deterministik lebih dahulu. Model AI hanya menjadi peningkat
akurasi untuk kasus ambigu, bukan satu-satunya gerbang.

## 6. Sentimen Bahasa Indonesia

Pipeline minimum:

```text
hapus URL dan mention
→ ubah hashtag menjadi kata
→ normalisasi slang
→ deteksi negasi
→ deteksi konstruksi retoris
→ klasifikasi
→ ekstraksi aspek
```

Kasus wajib dalam test:

- `enak banget` → positif.
- `tidak enak` → negatif.
- `nggak mengecewakan` → positif.
- `siapa sih yang nggak suka ini` → positif, bukan negatif.
- `akhirnya produk ini hadir` → positif/netral sesuai keseluruhan konteks.
- Caption promosi tanpa opini jelas → netral.
- Keluhan pengiriman tidak boleh otomatis mengubah opini rasa.

Strategi analyzer:

1. Gemini menghasilkan JSON terstruktur jika aktif dan budget tersedia.
2. Fallback lexicon/context lokal selalu tersedia.
3. Kegagalan Gemini tidak menghapus evidence.
4. Hasil menyimpan nama analyzer dan confidence.

## 7. Strategi hemat kuota

- Selalu baca snapshot database terlebih dahulu.
- Refresh hanya sumber yang stale atau diminta pengguna.
- Gunakan lock `(topic_id, source)` untuk mencegah run ganda.
- Terapkan TTL per sumber.
- Batasi query, jumlah hasil, polling, dan concurrency.
- Upsert evidence sebelum analisis untuk mencegah analisis item yang sama.
- Analisis hanya evidence baru atau evidence yang modelnya perlu diperbarui.
- Tampilkan usage provider pada endpoint internal/dashboard.
- Jika budget habis, simpan status `budget_exhausted` dan tetap tampilkan cache.

Tidak boleh merotasi credential untuk menghindari batas layanan atau melanggar
ketentuan provider. Pool key hanya untuk credential sah yang memang dimiliki tim.

## 8. Database minimum

Tabel inti:

```text
topics
source_runs
evidence
analyses
evidence_metric_snapshots
provider_usage
```

Index minimum:

- Unique `topics(id)`.
- Unique `evidence(source, topic_id, external_id)`.
- `evidence(topic_id, published_at DESC)`.
- `source_runs(topic_id, source, started_at DESC)`.
- Unique `analyses(evidence_id)` untuk hasil aktif POC.
- `provider_usage(provider, usage_date)`.

Database write hanya dilakukan backend. Schema Supabase yang terekspos harus
mengaktifkan RLS; browser tidak mendapat service-role key.

## 9. API minimum

```text
GET    /api/health
GET    /api/topics
POST   /api/topics
DELETE /api/topics/{topic_id}
GET    /api/topics/{topic_id}/snapshot
POST   /api/topics/{topic_id}/refresh
GET    /api/stream
```

Snapshot response menggabungkan:

- Topic aktif.
- Evidence terbaru dengan analisis.
- Status terakhir keenam sumber.
- Jumlah positif, negatif, netral, dan pending.
- Metrik/usage yang aman untuk ditampilkan.

Refresh harus segera mengembalikan status/ID run atau menyelesaikan pekerjaan
terbatas. Request browser tidak boleh menggantung menunggu polling provider yang
panjang.

## 10. UI dan perilaku loading

Sidebar dipisah per sumber dengan urutan:

1. TikTok
2. Instagram
3. Facebook
4. Google Maps
5. Shopee
6. YouTube

Aturan UI:

- Snapshot lama tidak dihapus ketika refresh dimulai.
- Tampilkan nama sumber yang sedang berjalan dan progres yang diketahui.
- `0 evidence`, `belum dikonfigurasi`, dan `gagal` harus dibedakan.
- Setiap evidence menyediakan link `Buka sumber`.
- Jangan menyebut data `live` tanpa timestamp koleksi dan status run.
- Desktop dan mobile tidak boleh overflow horizontal.

## 11. Error isolation dan observability

- Satu source adapter gagal tanpa membatalkan adapter lain.
- Error eksternal dipetakan ke kode stabil: `not_configured`,
  `provider_timeout`, `provider_permission`, `invalid_payload`,
  `database_timeout`, atau `budget_exhausted`.
- Log boleh memuat run ID dan source, tetapi tidak boleh memuat API key atau
  raw credential.
- Health endpoint membedakan process hidup dari dependency siap.
- Setiap run menyimpan count mentah, relevan, dan inserted agar dapat diaudit.

## 12. Pengujian wajib

- Contract validation untuk seluruh model.
- Parser fixture per provider tanpa network.
- Relevance false-positive dan true-positive.
- Sentimen negasi, slang, dan retoris Bahasa Indonesia.
- Repository upsert idempotent.
- Source failure isolation.
- Snapshot tetap tersedia selama refresh.
- API health/topic/snapshot/refresh.
- Secret scanning sederhana dan `.env` tidak terlacak Git.
- Smoke test deployment terhadap `/api/health`.

Live integration test harus diberi marker terpisah agar test normal tidak
menghabiskan kuota provider.
