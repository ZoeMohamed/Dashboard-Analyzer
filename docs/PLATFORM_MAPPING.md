# Mapping POC Scrapper → Dashboard Analyzer (Person 2)

Dokumen ini adalah peta implementasi integrator. Tujuannya mempertahankan
perilaku penting POC lama tanpa membawa SQLite, seed/demo data, atau route lama
yang tidak dipakai.

## Peta tanggung jawab

| Perilaku POC lama | Implementasi clean repo | Catatan |
| --- | --- | --- |
| Topic/product yang dipantau | `app/contracts.py:TopicCreate`, `app/database/repository.py` | ID slug stabil; nama dan keyword dinormalisasi. |
| Feed evidence lintas TikTok/Instagram/Facebook/Maps/Shopee/YouTube | `Evidence`, `SourceName`, `source_runs` | Adapter hanya mengirim evidence valid; route tidak scraping. |
| Deduplikasi evidence | constraint `(topic_id, source, external_id)` + `upsert_evidence` | Refresh berulang tidak menggandakan feed. |
| Status per sumber | `SourceRun`, `SourceSummary` | `queued → running → fresh/empty/error`; sumber gagal tidak membatalkan sumber lain. |
| Snapshot lama saat refresh | `PipelineService.start_refresh()` + repository snapshot | Refresh berjalan di background; UI tetap bisa membaca snapshot terakhir. |
| Rotasi/kuota provider | `Settings` + `UsageService` + `provider_usage` | Key hanya server-side; limit dijaga sebelum panggilan provider. |
| SSE progress | `EventBroker` + `GET /api/stream` | Queue dibatasi agar live feed tidak menghabiskan memori. |
| Persistensi | `PostgresRepository` + `migrations/0001_initial.sql` | Supabase/PostgreSQL; in-memory hanya fallback development/test. |
| Health/deployment | `app/main.py`, `GET /api/health`, `railway.json` | Railway menjalankan `uvicorn app.main:app`. |

## Kontrak frontend tim 4

Frontend Vite di `web/` memanggil:

```text
GET  /api/topics
GET  /api/topics/{topic_id}/snapshot
POST /api/topics/{topic_id}/refresh
```

`Snapshot` mengirim kontrak frontend baru (`sentiment`, `sources`, dan evidence
dengan `analysis` tersemat). Field ringkasan lama (`total_evidence`,
`positive_count`, `source_summaries`, dan lainnya) tetap tersedia sementara agar
merge bertahap tidak mematahkan konsumen lama.

Nama internal `maps` sengaja dipertahankan sebagai identifier API; UI memberi
label **Google Maps**. Ini mencegah breaking change pada branch frontend.

## Yang sengaja tidak dipindahkan

- SQLite dan database file lama.
- Seed/demo data dan replay otomatis yang dapat terlihat sebagai data live.
- API key, token Apify, Gemini, atau Google di source control.
- SQL di route, scraping di route, dan logika UI di repository.
- Klaim bahwa provider yang belum dikonfigurasi sudah aktif.

## Urutan integrasi branch

1. `team/2-platform` menyediakan kontrak, repository, migration, pipeline,
   usage guard, health, dan API dasar.
2. `team/1-sources` mendaftarkan provider ke `PipelineService.providers` dan
   mengembalikan `CollectionResult`.
3. `team/3-intelligence` mengisi `Analysis` setelah evidence lolos relevansi.
4. `team/4-frontend` membaca snapshot dan SSE tanpa menerima secret.

Setiap adapter harus bisa diuji dengan fixture tanpa memerlukan jaringan.
Production baru disebut live jika status source `fresh`/`empty` berasal dari
adapter provider yang terkonfigurasi, bukan dari fallback in-memory.
