# Final Output Blueprint

Dokumen ini menjelaskan dengan konkret seperti apa Dashboard Analyzer ketika selesai.
Ini adalah target hasil akhir, bukan deskripsi kondisi repository saat ini.
Semua anggota dan AI agent harus memakai dokumen ini untuk memastikan modul
yang dibuat dapat digabung menjadi satu aplikasi utuh.

## 1. Hasil akhir dalam satu kalimat

Dashboard Analyzer adalah aplikasi web yang menerima keyword produk UMKM, mengambil
evidence publik dari TikTok, Instagram, Facebook, Google Maps, Shopee, dan
YouTube, menyimpan hasil secara persisten, menyaring relevansi, menganalisis
sentimen Bahasa Indonesia, lalu menampilkan tren dan opini beserta link sumber
aslinya.

## 2. Pengalaman pengguna final

Ketika pengguna membuka aplikasi:

1. Snapshot terakhir langsung muncul dari database.
2. Pengguna melihat daftar produk yang sedang dipantau.
3. Sidebar memisahkan data TikTok, Instagram, Facebook, Google Maps, Shopee,
   dan YouTube.
4. Setiap sumber menunjukkan status terakhir dan jumlah evidence.
5. Pengguna dapat memilih produk atau menambahkan produk baru.
6. Pengguna dapat menekan **Refresh sumber**.
7. Snapshot lama tetap terlihat selama refresh.
8. UI menunjukkan sumber yang queued/running/sudah selesai/gagal.
9. Evidence baru muncul setelah disimpan dan dianalisis.
10. Pengguna dapat membuka URL asli untuk memverifikasi evidence.

Pengguna tidak perlu memahami Apify, Gemini, Supabase, atau sistem internal.

## 3. Tampilan dashboard final

### Header

Menampilkan:

- Nama aplikasi `Dashboard Analyzer`.
- Produk aktif.
- Waktu snapshot terakhir.
- Indikator koneksi/progress.
- Tombol `Pantau produk`.
- Tombol `Refresh sumber`.

### Sidebar sumber

Urutan tetap:

1. Ringkasan
2. TikTok
3. Instagram
4. Facebook
5. Google Maps
6. Shopee
7. YouTube

Setiap item menampilkan:

- Nama sumber.
- Jumlah evidence tersimpan.
- Status terakhir.
- Indikator fresh/stale/running/error.

### Ringkasan produk

Menampilkan:

- Total evidence.
- Jumlah positif.
- Jumlah negatif.
- Jumlah netral/pending.
- Aspek yang sering disebut.
- Distribusi evidence per sumber.
- Timestamp terakhir diperbarui.

### Halaman TikTok, Instagram, dan Facebook

Menampilkan:

- Caption/post yang relevan.
- Nama author jika tersedia.
- Tanggal publikasi.
- Views, likes, comments, dan shares jika tersedia.
- Sentimen dan confidence.
- Aspek yang disebut.
- Link `Buka sumber`.

Data sosial boleh kosong. UI harus membedakan:

- Belum pernah di-refresh.
- Provider belum dikonfigurasi.
- Refresh sedang berjalan.
- Refresh berhasil tetapi tidak ada hasil relevan.
- Provider gagal.

### Halaman Google Maps

Menampilkan dua bagian:

- Tempat/penjual relevan: nama, kota, rating, jumlah ulasan, dan link Maps.
- Feed opini produk: teks ulasan yang benar-benar menyebut produk.

Ulasan tempat umum yang tidak membahas produk tidak dimasukkan ke sentimen
produk.

### Halaman Shopee

Menampilkan:

- Judul produk.
- Nama toko jika tersedia.
- Harga dan harga awal jika tersedia.
- Rating dan jumlah rating.
- Jumlah terjual jika tersedia.
- URL produk.

Nilai yang tidak tersedia ditampilkan sebagai `—`, bukan dibuat-buat.

### Halaman YouTube

Menampilkan:

- Video yang lolos filter produk UMKM.
- Judul, channel, tanggal publikasi, dan URL.
- Views, likes, dan comments jika tersedia.
- Views per hari.
- Content type: review, resep, ide usaha, atau lainnya.
- Indikator supply dan attention jika snapshot metrik mencukupi.

Konten hiburan, kartun, episode, trailer, gameplay, dan konten anak yang hanya
kebetulan menyebut keyword produk harus ditolak.

## 4. Struktur repository final

```text
Dashboard-Analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── contracts.py
│   ├── errors.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   ├── health.py
│   │   ├── topics.py
│   │   ├── snapshot.py
│   │   ├── refresh.py
│   │   └── stream.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── repository.py
│   │
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── normalize.py
│   │   ├── relevance.py
│   │   ├── sentiment.py
│   │   ├── gemini.py
│   │   └── lexicon/
│   │       ├── positive.txt
│   │       ├── negative.txt
│   │       └── stopwords.txt
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── topics.py
│   │   ├── pipeline.py
│   │   ├── scheduler.py
│   │   ├── usage.py
│   │   └── events.py
│   │
│   └── sources/
│       ├── __init__.py
│       ├── base.py
│       ├── apify_client.py
│       ├── tiktok.py
│       ├── instagram.py
│       ├── facebook.py
│       ├── maps.py
│       ├── shopee.py
│       └── youtube.py
│
├── web/
│   ├── index.html
│   ├── styles/
│   │   ├── tokens.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   └── responsive.css
│   └── scripts/
│       ├── api.js
│       ├── state.js
│       ├── render.js
│       └── app.js
│
├── migrations/
│   └── 0001_initial.sql
│
├── tests/
│   ├── conftest.py
│   ├── contracts/
│   ├── api/
│   ├── database/
│   ├── intelligence/
│   ├── services/
│   ├── sources/
│   ├── e2e/
│   └── fixtures/
│       └── providers/
│
├── docs/
│   ├── SYSTEM.md
│   ├── TEAM.md
│   └── FINAL_OUTPUT.md
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── railway.json
```

Folder hanya dibuat ketika isinya mulai diimplementasikan. Jangan membuat
puluhan file kosong hanya untuk menyerupai tree ini.

## 5. Fungsi file root

### `README.md`

Entry point dokumentasi. Menjelaskan tujuan, scope, setup lokal, environment,
Railway, dan definition of done.

### `.gitignore`

Mencegah `.env`, virtual environment, cache, database lokal, logs, build output,
dan credential masuk Git.

### `.env.example`

Berisi nama variable dengan nilai kosong/contoh aman. Tidak berisi secret asli.
File ini menjadi daftar konfigurasi yang dibutuhkan aplikasi.

### `requirements.txt`

Berisi dependency production dengan versi terkunci. Dependency test dapat
dipisah hanya jika integrator memutuskan `requirements-dev.txt` diperlukan.

### `railway.json`

Mendefinisikan builder, start command, health check, timeout, dan restart policy.
Tidak menyimpan environment variable atau secret.

## 6. Fungsi file inti backend

### `app/__init__.py`

Menandai package Python. Tidak berisi side effect atau startup logic.

### `app/main.py`

Composition root aplikasi:

- Membuat instance FastAPI.
- Memasang middleware aman.
- Membuat repository, services, providers, dan event broker.
- Memasang router.
- Mengelola lifespan startup/shutdown.
- Menyajikan file dashboard.

`main.py` tidak berisi query SQL, parser provider, atau algoritma sentimen.

### `app/config.py`

Satu-satunya tempat membaca environment variables. Bertanggung jawab atas:

- Validasi mode development/production.
- Parsing daftar Gemini key secara aman.
- Konfigurasi database.
- Limit, timeout, TTL, dan usage budget.
- Daftar source aktif.

Nilai secret tidak boleh muncul di `repr`, log, atau response API.

### `app/contracts.py`

Kontrak Pydantic bersama:

- `Topic` dan `TopicCreate`.
- `Evidence` dan `EvidenceMetrics`.
- `Analysis`.
- `SourceRun`.
- `CollectionResult`.
- `Snapshot`.
- `StreamEvent`.
- Enum source, status, trigger, sentiment, analyzer, dan error code.

Semua tim meng-import model ini; tidak membuat versi kontrak sendiri.

### `app/errors.py`

Domain errors stabil:

- `NotConfiguredError`.
- `BudgetExhaustedError`.
- `ProviderTimeoutError`.
- `ProviderPermissionError`.
- `InvalidProviderPayloadError`.
- `TopicNotFoundError`.
- `TopicLimitError`.

Error ini dipetakan ke status run dan HTTP response tanpa membocorkan detail
credential.

## 7. Fungsi file API

### `app/api/dependencies.py`

Mengambil services dari `app.state` atau dependency container. Mencegah setiap
route membuat koneksi/provider sendiri.

### `app/api/health.py`

Endpoint:

```text
GET /api/health
```

Response minimal:

```json
{
  "ok": true,
  "service": "poc-scrapper",
  "version": "0.1.0"
}
```

Endpoint harus cepat dan tidak memanggil provider eksternal.

### `app/api/topics.py`

Endpoint:

```text
GET    /api/topics
POST   /api/topics
DELETE /api/topics/{topic_id}
```

Melakukan validasi HTTP dan memanggil topic service/repository. Tidak membuat
keyword dengan logika duplikat di route.

### `app/api/snapshot.py`

Endpoint:

```text
GET /api/topics/{topic_id}/snapshot
```

Mengembalikan topic, summary sentiment, evidence terbaru, source status, metrics,
dan timestamp. Membaca cache/database; tidak otomatis memulai scraping panjang.

### `app/api/refresh.py`

Endpoint:

```text
POST /api/topics/{topic_id}/refresh
```

Menerima daftar source opsional, memulai bounded refresh, dan mengembalikan run
status/ID. Endpoint dilindungi rate/budget dan optional `REFRESH_TOKEN` untuk
operasi internal production.

### `app/api/stream.py`

Endpoint SSE:

```text
GET /api/stream
```

Mengirim status/progress tanpa polling browser agresif. Event minimal:

- `source_status`.
- `evidence_new`.
- `analysis_updated`.
- `error`.
- `ping`.

Slow client tidak boleh memblokir pipeline.

## 8. Fungsi file database

### `app/database/connection.py`

Membuat dan menutup async PostgreSQL pool. Mengatur timeout, maximum pool size,
transaction helper, serta retry startup yang terbatas.

### `app/database/repository.py`

Satu lapisan untuk seluruh query:

- Create/list/deactivate topic.
- Create/update source run.
- Idempotent evidence upsert.
- Insert metric snapshot.
- Upsert analysis.
- Read snapshot dengan limit/pagination.
- Read/write provider usage.
- Purge data berdasarkan retention jika diperlukan.

Repository mengembalikan contracts/domain objects, bukan raw cursor ke route.

### `migrations/0001_initial.sql`

Membuat schema awal, constraints, indexes, timestamp types, dan RLS yang sesuai.
Migration tidak berisi API key atau seed data palsu.

Tabel final minimum:

```text
topics
source_runs
evidence
analyses
evidence_metric_snapshots
provider_usage
```

## 9. Fungsi file intelligence

### `app/intelligence/normalize.py`

Pure functions untuk:

- Lowercase/casefold.
- Hapus URL dan mention.
- Ubah hashtag menjadi token.
- Normalisasi spasi dan karakter berulang.
- Perluas slang Indonesia.
- Tokenisasi.

### `app/intelligence/relevance.py`

Menentukan apakah evidence berkaitan dengan produk. Menggunakan:

- Keyword phrase.
- Product terms.
- Exclude terms.
- Konteks produk/UMKM/perdagangan.
- Threshold score yang dapat diuji.

Mengembalikan keputusan, score, dan alasan singkat untuk debugging.

### `app/intelligence/sentiment.py`

Interface analyzer dan fallback lokal. Menangani:

- Lexicon positif/negatif.
- Negasi.
- Kalimat retoris.
- Label/score/confidence.
- Aspek harga, rasa, kualitas, kemasan, pelayanan, pengiriman, dan lainnya.

### `app/intelligence/gemini.py`

Adapter Gemini server-side:

- Prompt Bahasa Indonesia yang sempit.
- Structured JSON output.
- Batch bounded.
- Timeout dan quota error mapping.
- Validasi output dengan contracts.
- Fallback tanpa menghapus evidence.

### `app/intelligence/lexicon/*.txt`

Data kata lokal yang kecil dan dapat direview. Satu kata/frasa per baris.
Tidak berisi data hasil scraping.

## 10. Fungsi file services

### `app/services/topics.py`

Membuat slug, memastikan batas topik, membersihkan keywords/terms, dan memanggil
repository. Semua aturan topic berada di service ini.

### `app/services/pipeline.py`

Orchestrator utama:

```text
buat SourceRun queued
→ running
→ panggil adapter
→ relevance filter
→ evidence upsert
→ analysis
→ finish fresh/empty/error
→ publish event
```

Menjalankan sumber secara terisolasi. Satu exception tidak membatalkan sumber
lain. Lock diterapkan per `(topic_id, source)`.

### `app/services/scheduler.py`

Memeriksa source yang stale dan memicu refresh berdasarkan TTL. Untuk satu
replica POC. Tidak boleh membuat refresh tak terbatas saat startup.

### `app/services/usage.py`

Mencatat dan memeriksa batas penggunaan provider:

- Daily/monthly budget.
- Per-source run count.
- Quota/reserve yang relevan.
- Status `budget_exhausted`.

### `app/services/events.py`

Event broker non-blocking untuk SSE. Queue memiliki batas. Client lambat boleh
melewatkan event tetapi tidak memperlambat collector.

## 11. Fungsi file source adapters

### `app/sources/base.py`

Mendefinisikan `SourceAdapter` dan helper hasil collection. Tidak mengenal
FastAPI/UI.

### `app/sources/apify_client.py`

HTTP client bersama untuk:

- Memulai Actor run.
- Poll status dengan interval dan timeout bounded.
- Membaca dataset.
- Memetakan status/error Apify.
- Mencatat provider run ID dan usage.

Token selalu dikirim server-side dan tidak dicetak ke log.

### `app/sources/tiktok.py`

Membangun query TikTok terbatas, memanggil Actor, dan memetakan post menjadi
Evidence beserta metrics.

### `app/sources/instagram.py`

Memetakan caption/post Instagram publik menjadi Evidence. Author atau metrics
boleh `null` jika Actor tidak memberikannya.

### `app/sources/facebook.py`

Memetakan post Facebook publik. Tidak mencoba mengakses group/profile privat.

### `app/sources/maps.py`

Mencari tempat berdasarkan produk dan kota, lalu memetakan tempat/ulasan.
Evidence opini hanya dibuat dari review yang menyebut produk.

### `app/sources/shopee.py`

Memetakan listing produk Shopee. Menormalisasi harga dan count tanpa mengarang
nilai yang hilang.

### `app/sources/youtube.py`

Mencari video relevan, memuat detail/metrik, membuang konten excluded, dan
menentukan discovery/content metadata. Harus memiliki limit agar tidak boros
quota.

## 12. Fungsi file frontend

### `web/index.html`

Semantic shell dashboard: sidebar, header, topic controls, progress, summary,
source panels, dialog tambah topik, dan toast. Tidak berisi API key atau data
hardcoded yang diklaim live.

### `web/styles/tokens.css`

Color, typography, spacing, radius, border, shadow, dan motion tokens.

### `web/styles/layout.css`

App shell, sidebar, header, grid, panel, table/list, dan page structure.

### `web/styles/components.css`

Button, badge, status, evidence row, sentiment summary, empty state, loading,
dialog, toast, dan control states.

### `web/styles/responsive.css`

Breakpoint tablet/mobile. Menjamin 390px tidak overflow horizontal dan kontrol
tetap dapat digunakan.

### `web/scripts/api.js`

Satu wrapper `fetch`: base URL, JSON, timeout, error parsing, dan seluruh endpoint.

### `web/scripts/state.js`

State minimal: topics, active topic/source, snapshot, loading, connection, dan
filters. Tidak menyimpan secret/local credential.

### `web/scripts/render.js`

Pure-ish rendering helpers untuk source status, evidence, summary sentiment,
empty/error/loading states, dan escaped text.

### `web/scripts/app.js`

Bootstrap UI, event binding, topic selection, refresh action, SSE connection,
debounce update, dan orchestration render.

## 13. Fungsi test suite

### `tests/conftest.py`

Shared fixtures: settings tanpa secret, test app, fake repository, fake provider,
sample topic/evidence, dan isolated database jika diperlukan.

### `tests/contracts/`

Menguji validation, enum, datetime, bounds, dan serialization kontrak.

### `tests/sources/`

Menguji parser setiap provider menggunakan fixture lokal. Test default tidak
melakukan network.

### `tests/database/`

Menguji migration, constraints, idempotent upsert, pagination, topic isolation,
dan persistence.

### `tests/intelligence/`

Menguji slang, negasi, kalimat retoris, false-positive relevansi, aspects, dan
fallback Gemini.

### `tests/services/`

Menguji state transition SourceRun, lock, budget, error isolation, dan events.

### `tests/api/`

Menguji health, CRUD topic, snapshot, refresh, status code, dan safe error body.

### `tests/e2e/`

Menguji alur dashboard utama, filter sidebar, loading/error/empty, serta layout
desktop dan mobile.

### `tests/fixtures/providers/`

Potongan payload provider yang sudah disanitasi. Fixture harus kecil, stabil,
tanpa credential, dan jelas dilabel sebagai test data.

## 14. Perilaku runtime final

### Startup

```text
load config
→ validate required production config
→ open database pool
→ construct repository/services/providers
→ mount API and dashboard
→ start bounded scheduler
→ health ready
```

Startup tidak melakukan scraping seluruh topik.

### Membuka dashboard

```text
GET topics
→ pilih topik aktif
→ GET snapshot database
→ render snapshot
→ connect SSE
```

Dashboard tidak menunggu provider eksternal.

### Menambah topik

```text
user submits name + city
→ validate
→ create keywords/product terms
→ persist Topic
→ show empty/not-yet-refreshed source state
→ optional bounded refresh
```

### Refresh

```text
POST refresh
→ validate topic/source/budget
→ create run(s)
→ return status to browser
→ collectors execute
→ filter/upsert/analyze
→ SSE updates UI
→ snapshot remains visible
```

### Restart/deployment

Setelah process restart, topic, evidence, analyses, dan run history dibaca dari
PostgreSQL. Hanya connection/event subscribers/locks lokal yang diinisialisasi
ulang.

## 15. Contoh snapshot API final

```json
{
  "topic": {
    "id": "cappuccino-cincau",
    "name": "Cappuccino Cincau",
    "cities": ["Bandung"]
  },
  "generated_at": "2026-10-03T03:00:00Z",
  "sentiment": {
    "positif": 18,
    "negatif": 3,
    "netral": 7,
    "pending": 2
  },
  "sources": [
    {
      "source": "instagram",
      "status": "fresh",
      "evidence_count": 12,
      "last_finished_at": "2026-10-03T02:58:00Z",
      "message": null
    }
  ],
  "evidence": [
    {
      "id": "instagram:post-123",
      "source": "instagram",
      "title": "nama-akun",
      "text": "caption yang relevan dengan produk",
      "url": "https://instagram.com/p/post-123",
      "published_at": "2026-10-02T10:00:00Z",
      "metrics": {
        "views": null,
        "likes": 25,
        "comments": 4,
        "shares": null
      },
      "analysis": {
        "label": "positif",
        "score": 0.8,
        "confidence": 0.91,
        "aspects": ["rasa"],
        "analyzer": "gemini"
      }
    }
  ]
}
```

Response aktual boleh menambah field, tetapi tidak boleh mengubah arti field
bersama tanpa memperbarui contracts, tests, dan dokumentasi.

## 16. Kondisi gagal yang harus tetap usable

### APIFY_TOKEN tidak ada

- Health tetap hidup.
- Source terkait berstatus `misconfigured`.
- Snapshot lama tetap tampil.
- UI tidak meminta token kepada browser.

### Gemini quota habis

- Evidence tetap disimpan.
- Fallback lokal digunakan atau analysis tetap pending.
- UI menunjukkan analyzer/fallback secara jujur.
- Source collection tidak ditandai gagal hanya karena analysis gagal.

### Satu Actor timeout

- Run sumber tersebut menjadi `error` dengan `provider_timeout`.
- Sumber lain tetap berjalan.
- Snapshot lama sumber yang gagal tidak dihapus.

### Database sementara gagal

- API mengembalikan error aman tanpa connection string.
- Provider refresh tidak terus menghabiskan kuota ketika persistence tidak siap.
- Health/readiness melaporkan dependency failure sesuai desain.

### Provider memberi payload berubah

- Item invalid dilewati atau run diberi `invalid_payload` sesuai tingkat masalah.
- Raw secret tidak masuk log.
- Fixture baru ditambahkan sebelum parser diperbaiki.

## 17. Definition of complete per lapisan

### Contracts complete

- Semua enum dan model tervalidasi.
- Serialization JSON konsisten.
- Keempat anggota memakai file yang sama.

### Sources complete

- Enam adapter tersedia.
- Parser fixture lulus.
- Timeout/limit/error mapping diterapkan.
- Minimal sumber yang benar-benar configured lolos live smoke test terbatas.

### Platform complete

- Migration dapat dijalankan pada database kosong.
- Topic/evidence/analysis/run persisten.
- Deduplikasi bekerja.
- Snapshot query bounded.
- Usage budget tercatat.

### Intelligence complete

- False-positive utama ditolak.
- Negasi dan retoris Indonesia dites.
- Gemini structured output tervalidasi.
- Fallback lokal bekerja.

### API/frontend complete

- Semua endpoint minimum tersedia.
- Sidebar dan source filtering bekerja.
- Loading/error/empty berbeda.
- Evidence memiliki URL sumber.
- Tidak ada overflow mobile atau console error.

### Deployment complete

- Railway build berhasil.
- `/api/health` HTTP 200 pada public domain.
- Supabase migration dan connection berhasil.
- Secret hanya ada di Railway/Supabase.
- Restart tidak menghilangkan data.
- Smoke test topik → refresh → snapshot → buka evidence berhasil.

## 18. Demo final untuk juri

Urutan demo ideal maksimal beberapa menit:

1. Buka dashboard dan tunjukkan snapshot langsung muncul.
2. Pilih produk yang sudah memiliki evidence.
3. Tunjukkan ringkasan positif/negatif/netral.
4. Buka sidebar Instagram/TikTok dan link evidence asli.
5. Tunjukkan Google Maps untuk opini pelanggan.
6. Tunjukkan Shopee untuk sinyal produk/penjualan.
7. Tunjukkan YouTube di bagian akhir sebagai tren konten.
8. Tekan refresh terbatas dan tunjukkan progress tanpa blank screen.
9. Jelaskan cache database menghemat token/Apify.
10. Tunjukkan satu test sentimen konteks Bahasa Indonesia.

Jangan menghabiskan waktu demo menunggu provider lama. Gunakan snapshot nyata
yang sudah tersimpan dan refresh terbatas sebagai bukti proses live.

## 19. Hal yang tidak boleh ada pada hasil final

- API key di Git, browser, screenshot, atau log.
- Label `live` pada fixture/demo data.
- Angka metrics palsu untuk field provider yang kosong.
- SQL langsung di route.
- Fetch Apify/Gemini dari frontend.
- Semua logic dalam satu file besar.
- Scraping otomatis tak terbatas saat startup.
- Blank dashboard selama refresh.
- Satu provider error membuat seluruh aplikasi gagal.
- SQLite production tanpa persistent volume.
- Folder/file lama yang tidak digunakan hanya karena berasal dari legacy.

## 20. Cara AI menggunakan blueprint ini

AI agent harus:

1. Membaca empat dokumen resmi.
2. Menentukan perannya dari `docs/TEAM.md`.
3. Mencari file target perannya dalam struktur dokumen ini.
4. Membuat hanya file yang diperlukan untuk task saat itu.
5. Mengikuti contracts nyata di `app/contracts.py` ketika file tersebut tersedia.
6. Menjalankan test ownership-nya.
7. Melaporkan deviasi dari blueprint kepada integrator.

Blueprint ini menjelaskan tujuan akhir, tetapi tidak memberi izin kepada satu
agent untuk membuat atau mengubah seluruh repository di luar ownership-nya.
