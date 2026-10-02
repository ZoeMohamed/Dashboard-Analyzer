# Team Workflow — 4 Orang

Dokumen ini mengatur pekerjaan paralel empat anggota selama clean rebuild.
Setiap anggota wajib membaca `README.md`, `docs/SYSTEM.md`, dan
`docs/FINAL_OUTPUT.md` sebelum dokumen ini.

## 1. Aturan bersama

- `main` harus selalu dapat dijalankan dan dites.
- Satu orang hanya mengubah area ownership-nya kecuali sudah berkoordinasi.
- `app/contracts.py` dan `app/main.py` hanya diubah integrator.
- Jangan commit `.env`, API key, token, dataset besar, atau raw response sensitif.
- Jangan menggunakan data palsu sebagai data live.
- Semua adapter diuji dengan fixture lokal sebelum live test.
- Pull request dibuat kecil dan tidak mencampur refactor yang tidak relevan.
- Rebase/merge `main` sebelum handoff agar konflik ditemukan lebih awal.

## 2. Branch dari baseline bersih

Setelah integrator menyelesaikan kontrak awal, buat branch berikut dari `main`:

```text
team/1-sources
team/2-platform
team/3-intelligence
team/4-frontend
```

Perintah setiap anggota:

```bash
git switch main
git pull --ff-only origin main
git switch -c team/NAMA-BRANCH
git push -u origin team/NAMA-BRANCH
```

Jangan membuat branch dari `archive/legacy-poc`.

## 3. Anggota 1 — Source adapters

### Tujuan

Mengubah hasil provider menjadi `Evidence` yang konsisten tanpa menyentuh
database atau UI.

### Ownership

```text
app/sources/__init__.py
app/sources/base.py
app/sources/apify_client.py
app/sources/tiktok.py
app/sources/instagram.py
app/sources/facebook.py
app/sources/maps.py
app/sources/shopee.py
app/sources/youtube.py
tests/fixtures/providers/
tests/sources/
```

### Output wajib

- Interface `SourceAdapter` sesuai `app/contracts.py`.
- Parser fixture untuk enam sumber.
- Timeout dan error mapping konsisten.
- Bounded input: query, limit, concurrency, dan polling.
- Tidak ada API key hardcoded.
- Tidak ada database query atau HTML di adapter.

### Test minimum

- Payload valid dipetakan dengan benar.
- Field yang hilang tidak membuat seluruh batch gagal.
- ID eksternal stabil.
- URL dan timestamp dinormalisasi.
- Metrics yang tidak tersedia tetap `null`.

## 4. Anggota 2 — Platform, database, orchestration, dan integrator

### Tujuan

Menjadi team lead/integrator serta menyediakan fondasi bersama, database
persisten, pipeline idempotent, usage budget, dan status run yang dapat dibaca
API.

### Ownership

```text
app/database/__init__.py
app/database/connection.py
app/database/repository.py
app/services/pipeline.py
app/services/usage.py
app/config.py
app/contracts.py
app/main.py
migrations/
tests/database/
tests/services/
tests/contracts/
tests/test_health.py
requirements.txt
.env.example
railway.json
```

### Output wajib

- Schema untuk topic, evidence, analysis, source run, metrics, dan usage.
- Unique constraint untuk deduplikasi evidence.
- Repository tanpa SQL di route.
- Refresh lock per topic/source.
- Snapshot-first dan stale refresh.
- Transaction pada perubahan status dan data penting.
- Migration aman untuk PostgreSQL/Supabase.
- Fondasi contracts, health endpoint, configuration, dependency, dan Railway.

### Test minimum

- Upsert yang sama dua kali tidak membuat duplikasi.
- Snapshot bertahan setelah restart database.
- Run satu topik tidak bocor ke topik lain.
- Error satu sumber tidak membatalkan sumber lain.
- Query snapshot memiliki pagination/limit.

## 5. Anggota 3 — Intelligence dan sentimen

### Tujuan

Memastikan hanya evidence relevan yang disimpan/ditampilkan dan sentimen
memahami konteks Bahasa Indonesia.

### Ownership

```text
app/intelligence/__init__.py
app/intelligence/normalize.py
app/intelligence/relevance.py
app/intelligence/sentiment.py
app/intelligence/gemini.py
app/intelligence/lexicon/
tests/intelligence/
```

### Output wajib

- Normalisasi URL, mention, hashtag, karakter berulang, dan slang.
- Filter keyword + product context + exclude term.
- Negation window.
- Deteksi kalimat retoris umum Indonesia.
- Gemini structured output dengan fallback lokal.
- Label, score, confidence, aspects, dan analyzer name.
- Tidak melakukan scraping atau query UI.

### Test minimum

- Konten Upin & Ipin tentang ayam ditolak untuk topik produk ayam.
- Review/promo produk ayam UMKM diterima.
- `siapa sih yang nggak suka` tidak menjadi negatif.
- `tidak enak` negatif dan `nggak mengecewakan` positif.
- Kegagalan Gemini menggunakan fallback tanpa kehilangan evidence.

## 6. Anggota 4 — API dan frontend

### Tujuan

Menyediakan API tipis dan dashboard yang menjelaskan data, progress, serta error
secara jujur.

### Ownership

```text
app/api/__init__.py
app/api/health.py
app/api/topics.py
app/api/snapshot.py
app/api/refresh.py
app/api/stream.py
web/
tests/api/
tests/e2e/
```

### Output wajib

- Endpoint sesuai `docs/SYSTEM.md`.
- Sidebar per sumber dengan sosial di atas dan YouTube di bawah.
- Snapshot lama tetap terlihat saat refresh.
- Loading, empty, misconfigured, budget exhausted, dan error state.
- Filter evidence per sumber.
- Link ke URL asli.
- Responsive desktop dan mobile.
- Browser tidak menerima secret.

### Test minimum

- Health dan topic CRUD.
- Snapshot response dirender.
- Pergantian sumber memfilter evidence.
- Refresh menampilkan progres tanpa mengosongkan list.
- Mobile 390px tidak memiliki horizontal overflow.
- Error API menghasilkan pesan yang dapat dipahami pengguna.

## 7. File milik integrator (Anggota 2)

Anggota 2 merangkap integrator. Hanya Anggota 2 yang mengubah:

```text
app/contracts.py
app/main.py
requirements.txt
.env.example
railway.json atau Dockerfile
README.md
docs/SYSTEM.md
docs/TEAM.md
docs/FINAL_OUTPUT.md
```

Integrator bertanggung jawab atas:

- Menetapkan kontrak sebelum pekerjaan paralel.
- Menggabungkan pull request sesuai dependency.
- Menjalankan seluruh test setelah setiap merge.
- Memastikan environment lokal dan Railway memakai konfigurasi yang sama.
- Menjaga empat dokumen Markdown utama tetap konsisten.
- Menghubungkan repository GitHub ke Railway dan mengelola production variables.
- Menjalankan migration production serta smoke test setelah deployment.

Anggota tim tidak memasukkan atau mengubah credential production. Jika sebuah
fitur memerlukan variable baru, anggota hanya menambah nama dan dokumentasinya
ke `.env.example` melalui permintaan kepada integrator.

## 8. Urutan integrasi

Urutan merge yang disarankan:

1. Integrator: contracts, config skeleton, FastAPI health, dan test foundation.
2. Anggota 3: normalisasi dan filter murni tanpa dependency eksternal.
3. Anggota 2: schema, repository, dan pipeline berdasarkan contracts.
4. Anggota 1: source adapters ke pipeline.
5. Anggota 4: API dan UI berdasarkan snapshot contract.
6. Integrator: live wiring, Railway, security check, dan demo smoke test.

Anggota tetap bekerja paralel. Urutan di atas adalah urutan merge, bukan alasan
untuk menunggu tanpa bekerja.

## 9. Jadwal live coding empat jam

### 00:00–00:30 — Fondasi bersama

- Semua membaca empat dokumen.
- Integrator membuat contracts, health endpoint, config, dan test command.
- Semua branch dibuat dari commit fondasi yang sama.

### 00:30–02:00 — Implementasi paralel

- Anggota 1 membuat adapter + fixture parser.
- Anggota 2 membuat migration + repository + pipeline.
- Anggota 3 membuat relevance + sentiment.
- Anggota 4 membuat API/UI dengan fixture contract.

### 02:00–03:00 — Integrasi

- Merge intelligence dan platform.
- Merge adapters.
- Hubungkan API/UI.
- Perbaiki conflict pada integrator, bukan dengan force-push.

### 03:00–03:40 — Verifikasi

- Unit dan integration test.
- Test dua keyword berbeda.
- Test source failure dan empty state.
- Test mobile.
- Test Railway health endpoint.

### 03:40–04:00 — Demo

- Bersihkan log dan data uji.
- Pastikan status data live/cache jelas.
- Latihan alur: buat topik → refresh → evidence → sentimen → buka sumber.

## 10. Format commit dan pull request

Contoh commit:

```text
feat(sources): add Instagram evidence parser
feat(database): add idempotent evidence repository
feat(intelligence): handle Indonesian rhetorical negation
feat(web): show per-source refresh progress
test(api): cover snapshot empty state
fix(pipeline): isolate provider timeout
```

Pull request wajib menjawab:

```text
Tujuan:
File ownership:
Kontrak yang digunakan/diubah:
Cara menguji:
Hasil test:
Risiko atau pekerjaan tersisa:
```

## 11. Checklist sebelum handoff

- Branch berasal dari `main` clean.
- Tidak ada perubahan di luar ownership tanpa catatan.
- Tidak ada secret atau `.env` yang terlacak.
- Fixture tidak disebut data live.
- Test area sendiri lulus.
- Formatter/linter lulus ketika sudah dikonfigurasi.
- Error provider tidak ditelan tanpa status.
- README/SYSTEM diperbarui jika perilaku publik berubah.
- Commit sudah dipush dan nama branch disampaikan ke integrator.

## 12. Prompt awal untuk AI agent

Gunakan prompt sesuai anggota. Kirim prompt sebagai pesan pertama setelah AI
dibuka pada folder repository. Jangan memendekkan bagian root, dokumen, branch,
ownership, test, atau format laporan.

### Urutan membuka empat AI agent

1. Setiap anggota memakai clone atau worktree sendiri. Jangan membuka empat
   agent pada working directory yang sama karena perpindahan branch dan file
   sementara akan saling mengganggu.
2. Path `/Users/zoemohamed/project/Dashboard-Analyzer` berlaku pada komputer utama.
   Anggota di komputer lain menggantinya dengan root clone masing-masing dan
   memverifikasi remote menunjuk ke `ZoeMohamed/Dashboard-Analyzer`.
3. Kirim prompt Anggota 2 terlebih dahulu. Tunggu fondasi masuk ke `main` dan
   salin nilai `FOUNDATION_SHA` dari laporannya.
4. Buat `team/1-sources`, `team/2-platform`, `team/3-intelligence`, dan
   `team/4-frontend` tepat dari `FOUNDATION_SHA`, lalu push branch tersebut.
5. Masukkan `FOUNDATION_SHA` nyata ke prompt Anggota 1, 3, dan 4, kemudian
   jalankan ketiganya secara paralel pada workspace masing-masing.
6. Setelah membagikan SHA, Anggota 2 pindah ke `team/2-platform` untuk membuat
   database dan pipeline. Integrasi kembali ke `main` mengikuti Bagian 8.

Contoh yang dijalankan integrator setelah fondasi selesai:

```bash
git switch main
git pull --ff-only origin main
git branch team/1-sources FOUNDATION_SHA
git branch team/2-platform FOUNDATION_SHA
git branch team/3-intelligence FOUNDATION_SHA
git branch team/4-frontend FOUNDATION_SHA
git push origin team/1-sources team/2-platform team/3-intelligence team/4-frontend
```

Ganti teks `FOUNDATION_SHA` dengan SHA yang dilaporkan, bukan nama literal.

### Prompt awal Anggota 2 — Integrator dan fondasi

Prompt ini dijalankan pertama kali sebelum tiga anggota lain mulai coding.

```text
Anda adalah Anggota 2 sekaligus integrator/team lead clean rebuild Dashboard Analyzer.

ROOT REPOSITORY RESMI:
/Users/zoemohamed/project/Dashboard-Analyzer

Repository lama /Users/zoemohamed/project/poc_python dan branch
archive/legacy-poc bukan fondasi implementasi. Jangan menyalin file atau
arsitektur lama kecuali saya secara eksplisit meminta referensi perilaku.

TUJUAN TURN PERTAMA:
Membuat fondasi executable bersama agar tiga AI agent lain dapat bekerja dari
kontrak dan test yang sama. Pada turn pertama ini jangan membangun seluruh
database, scraper, intelligence, atau UI.

LANGKAH WAJIB SEBELUM EDIT:
1. Pastikan current working directory tepat di root resmi di atas.
2. Jalankan pemeriksaan read-only: pwd, git status, git branch --show-current,
   git log -1 --oneline, dan daftar file maksimal depth 3.
3. Branch harus main dan working tree harus bersih. Jika tidak, berhenti dan
   laporkan kondisi sebenarnya; jangan reset atau menghapus perubahan.
4. Baca EMPAT file berikut secara penuh, bukan hanya ringkasan:
   - README.md
   - docs/SYSTEM.md
   - docs/FINAL_OUTPUT.md
   - docs/TEAM.md
5. Ringkas secara internal kontrak, scope, ownership, dan definition of done.

OWNERSHIP ANDA:
- app/contracts.py
- app/config.py
- app/main.py
- app/errors.py jika dibutuhkan oleh contracts
- app/database/**
- app/services/pipeline.py
- app/services/usage.py
- migrations/**
- tests/contracts/**
- tests/database/**
- tests/services/**
- tests/test_health.py
- requirements.txt
- .env.example
- railway.json
- empat dokumen resmi ketika harus diselaraskan

OUTPUT KHUSUS TURN PERTAMA:
1. Buat package app minimal dengan __init__.py.
2. Buat app/contracts.py yang mengimplementasikan kontrak Topic, TopicCreate,
   EvidenceMetrics, Evidence, Analysis, SourceRun, CollectionResult, Snapshot,
   StreamEvent, SourceName, SourceStatus, sentiment, analyzer, trigger, dan
   error code sesuai docs/SYSTEM.md dan docs/FINAL_OUTPUT.md.
3. Buat app/config.py menggunakan pydantic-settings. Secret harus memiliki
   representasi aman dan semua limit memiliki default POC bounded.
4. Buat app/main.py dengan FastAPI, GET /api/health, dan composition skeleton.
   Health tidak boleh memanggil provider eksternal.
5. Buat requirements.txt dengan versi dependency terkunci yang benar-benar
   dipakai fondasi.
6. Buat .env.example hanya berisi nama/contoh aman tanpa secret.
7. Buat railway.json dengan app.main:app, 0.0.0.0, $PORT, dan /api/health.
8. Buat contract tests dan health API test.
9. Jangan membuat dummy evidence yang diklaim live.
10. Jangan melakukan migration remote atau mengubah Supabase/Railway production.

QUALITY GATE:
- Seluruh model menolak source/status/score/URL yang invalid.
- Evidence mewajibkan title atau text.
- Datetime dinormalisasi timezone-aware.
- CollectionResult dapat menyimpan raw/relevant count dan provider run ID.
- Health response stabil dan testable.
- Import app tidak melakukan network atau membaca credential production.
- pytest lulus dari root repo.
- git diff --check lulus.
- Tidak ada .env/API key/token yang terlacak.

ATURAN KERJA:
- Gunakan apply_patch untuk edit file.
- Jangan menghapus file milik pengguna atau menjalankan reset --hard.
- Jangan membuat framework kedua atau abstraction yang belum dibutuhkan.
- Jangan mengubah public contract diam-diam setelah agent lain mulai.
- Jika keputusan kontrak tidak dijelaskan dokumen, pilih bentuk paling kecil
  yang mendukung final output dan catat asumsi.
- Jangan membuka pull request atau merge branch agent lain pada turn ini.

SELESAI TURN PERTAMA:
1. Jalankan seluruh test yang tersedia.
2. Tampilkan daftar file yang dibuat/diubah.
3. Commit dengan pesan: feat(platform): initialize shared application foundation
4. Push main hanya jika working tree awal bersih dan seluruh test lulus.
5. Laporkan commit SHA sebagai FOUNDATION_SHA.
6. Jangan lanjut ke database/pipeline penuh sebelum foundation SHA diberikan
   kepada anggota 1, 3, dan 4.

FORMAT LAPORAN AKHIR:
- Outcome
- FOUNDATION_SHA
- Contracts yang ditetapkan
- File dibuat/diubah
- Command test dan hasil
- Environment variable names (tanpa nilai)
- Asumsi
- Blocker/pekerjaan berikutnya

Mulai dengan pemeriksaan repository dan pembacaan empat dokumen. Jangan edit
sebelum kedua langkah itu selesai.
```

### Prompt awal Anggota 1 — Source adapters

Jalankan setelah integrator memberikan `FOUNDATION_SHA`.

```text
Anda adalah Anggota 1, pemilik source adapters Dashboard Analyzer.

ROOT REPOSITORY RESMI:
/Users/zoemohamed/project/Dashboard-Analyzer

BRANCH WAJIB:
team/1-sources

Repository lama /Users/zoemohamed/project/poc_python, folder .kilo/worktrees,
dan branch archive/legacy-poc bukan source of truth. Jangan menyalin kode lama.

LANGKAH WAJIB SEBELUM EDIT:
1. Pastikan pwd sama dengan root resmi.
2. Periksa git status, current branch, dan commit terakhir.
3. Branch harus team/1-sources, working tree bersih, dan branch harus mengandung
   FOUNDATION_SHA terbaru dari integrator. Jika tidak, berhenti dan laporkan.
4. Baca penuh:
   - README.md
   - docs/SYSTEM.md
   - docs/FINAL_OUTPUT.md
   - docs/TEAM.md
   - app/contracts.py
   - app/config.py
5. Jangan mulai sebelum memahami bentuk Topic, Evidence, CollectionResult,
   SourceRun, dan error code yang sudah ditetapkan.

TUJUAN ANDA:
Membuat adapter TikTok, Instagram, Facebook, Google Maps, Shopee, dan YouTube
yang mengubah payload provider menjadi Evidence seragam. Fokus pada parser,
bounded provider client, URL/timestamp/metrics mapping, dan error mapping.

OWNERSHIP EKSKLUSIF:
- app/sources/__init__.py
- app/sources/base.py
- app/sources/apify_client.py
- app/sources/tiktok.py
- app/sources/instagram.py
- app/sources/facebook.py
- app/sources/maps.py
- app/sources/shopee.py
- app/sources/youtube.py
- tests/sources/**
- tests/fixtures/providers/**

JANGAN EDIT:
- app/contracts.py
- app/config.py
- app/main.py
- app/database/**
- app/intelligence/**
- app/api/**
- app/services/**
- web/**
- requirements.txt, railway.json, atau dokumentasi

Jika dependency atau perubahan contract diperlukan, jangan edit sendiri.
Laporkan request kecil dan spesifik kepada integrator.

IMPLEMENTASI TURN AWAL:
1. Buat SourceAdapter Protocol/base interface sesuai contracts.
2. Buat parser pure function per sumber sebelum live HTTP integration.
3. Tambahkan fixture payload kecil dan disanitasi untuk enam sumber.
4. Buat Apify client bounded: timeout, polling interval, maximum polls,
   cancellation, dataset limit, provider run ID, dan error mapping.
5. Setiap adapter menerima Topic dan limit, lalu mengembalikan CollectionResult.
6. Jangan melakukan sentiment atau database upsert.
7. Jangan menyimpulkan data relevan akhir; adapter boleh memberi kandidat,
   intelligence layer menentukan relevansi final.
8. Maps hanya memetakan ulasan yang tersedia; jangan membuat teks ulasan.
9. Shopee tidak membuat angka harga/rating/sold count jika field hilang.
10. YouTube memiliki exclude/query bounds dan tidak mengambil komentar masal.

TEST WAJIB:
- Payload valid setiap sumber menjadi Evidence sesuai contracts.
- Missing optional fields menghasilkan null, bukan crash/angka palsu.
- External ID deterministik dan stabil.
- URL valid dan datetime timezone-aware.
- Duplikasi raw item dideduplikasi dalam hasil batch bila diperlukan.
- Provider timeout/permission/invalid payload dipetakan ke domain error.
- Test default tidak melakukan network.
- Tidak ada fixture yang dilabel sebagai data live.

ATURAN NETWORK DAN SECRET:
- Jangan menjalankan Actor/live scraping sampai semua fixture tests lulus.
- Live smoke test hanya jika integrator menyatakan credential tersedia dan
  memberi batas satu query kecil.
- Jangan membaca atau mencetak nilai token.
- Jangan menaruh token pada fixture, URL query, log, atau commit.

QUALITY GATE DAN HANDOFF:
1. Jalankan test ownership dan contract tests.
2. Jalankan git diff --check.
3. Periksa git diff hanya berisi ownership Anda.
4. Commit kecil dengan prefix feat(sources), test(sources), atau fix(sources).
5. Push hanya branch team/1-sources; jangan merge main.

FORMAT LAPORAN AKHIR:
- Outcome
- Branch dan commit SHA
- Adapter yang selesai
- Fixture/test yang dibuat
- Command test dan hasil
- Nama variable/dependency yang diminta (tanpa nilai)
- Assumption dan unsupported fields
- Blocker
- Instruksi singkat integrasi untuk Anggota 2

Mulai dengan pemeriksaan repo dan pembacaan dokumen. Jangan edit file di luar
ownership meskipun menurut Anda akan lebih cepat.
```

### Prompt awal Anggota 3 — Intelligence dan sentimen

Jalankan setelah integrator memberikan `FOUNDATION_SHA`.

```text
Anda adalah Anggota 3, pemilik intelligence, relevance, dan sentimen Bahasa
Indonesia untuk Dashboard Analyzer.

ROOT REPOSITORY RESMI:
/Users/zoemohamed/project/Dashboard-Analyzer

BRANCH WAJIB:
team/3-intelligence

Jangan menggunakan /Users/zoemohamed/project/poc_python, .kilo/worktrees, atau
archive/legacy-poc sebagai source of truth.

LANGKAH WAJIB SEBELUM EDIT:
1. Verifikasi pwd, git status, branch, dan commit terakhir.
2. Branch harus team/3-intelligence, working tree bersih, dan mengandung
   FOUNDATION_SHA integrator.
3. Baca penuh README.md, docs/SYSTEM.md, docs/FINAL_OUTPUT.md, docs/TEAM.md,
   app/contracts.py, dan app/config.py.
4. Catat contract Analysis, Evidence, sentiment label, analyzer name, score,
   confidence, aspects, dan error behavior.

TUJUAN ANDA:
Membuat pipeline pure/testable untuk normalisasi Bahasa Indonesia, filter
relevansi produk UMKM, sentimen kontekstual, ekstraksi aspek, Gemini structured
output, dan fallback lokal.

OWNERSHIP EKSKLUSIF:
- app/intelligence/__init__.py
- app/intelligence/normalize.py
- app/intelligence/relevance.py
- app/intelligence/sentiment.py
- app/intelligence/gemini.py
- app/intelligence/lexicon/**
- tests/intelligence/**

JANGAN EDIT:
- app/contracts.py, app/config.py, app/main.py
- app/sources/**, app/database/**, app/api/**, app/services/**
- web/**, requirements.txt, railway.json, atau dokumentasi

Jika contract/dependency perlu berubah, kirim request kepada integrator dengan
alasan, bentuk perubahan minimal, dan test yang memerlukannya.

IMPLEMENTASI TURN AWAL:
1. Normalisasi URL, mention, hashtag, repeated characters, case, whitespace,
   emoji-safe text, dan slang Indonesia yang disepakati.
2. Relevance filter deterministik: hard exclusion, product phrase/terms,
   commerce/UMKM context, score, threshold, dan alasan keputusan.
3. Pastikan konten Upin & Ipin/kartun/episode tentang ayam ditolak untuk topik
   produk ayam jika tidak memiliki konteks produk UMKM.
4. Buat sentiment analyzer fallback lokal dengan negation window dan aspek.
5. Tangani konstruksi retoris: “siapa sih yang nggak suka” bukan negatif.
6. Tangani double negation sederhana: “nggak mengecewakan” positif.
7. Caption promosi tanpa opini jelas sebaiknya netral.
8. Buat Gemini adapter yang meminta JSON terstruktur dan memvalidasi hasil
   melalui contracts; tidak boleh dipercaya tanpa validation.
9. Jika Gemini timeout/quota/invalid JSON, fallback lokal bekerja atau analysis
   tetap pending sesuai kontrak. Evidence tidak boleh hilang.
10. Batasi batch, concurrency, timeout, dan jumlah aspek.

TEST WAJIB:
- enak banget → positif.
- tidak enak → negatif.
- nggak mengecewakan → positif.
- siapa sih yang nggak suka ini → positif.
- akhirnya produk ini hadir → tidak otomatis negatif.
- caption promosi tanpa opini → netral.
- complaint pengiriman mengekstrak aspek pengiriman, bukan mengubah aspek rasa.
- false-positive kartun ditolak.
- review/promo produk UMKM relevan diterima.
- malformed Gemini JSON menggunakan fallback.
- Tidak ada network pada default tests.

QUALITY DAN KEAMANAN:
- Pure functions tidak membaca environment langsung.
- Gemini key hanya diterima melalui config/dependency injection.
- Prompt tidak berisi raw secrets atau data lebih banyak dari yang diperlukan.
- Jangan membuat klaim confidence palsu; formula/fallback harus terdokumentasi
  lewat kode dan test.
- Jangan scraping atau query database dari intelligence layer.

HANDOFF:
1. Jalankan tests/intelligence dan contract tests.
2. Jalankan git diff --check dan periksa ownership.
3. Commit dengan prefix feat(intelligence), test(intelligence), atau
   fix(intelligence).
4. Push hanya team/3-intelligence; jangan merge main.

FORMAT LAPORAN AKHIR:
- Outcome
- Branch dan commit SHA
- Algoritma yang dibuat
- Daftar kasus Bahasa Indonesia yang lulus
- Command test dan hasil
- Request dependency/contract jika ada
- Limitasi dan asumsi
- Instruksi integrasi untuk Anggota 2

Mulai dengan membaca dan memverifikasi, baru menulis kode.
```

### Prompt awal Anggota 4 — API dan frontend

Jalankan setelah integrator memberikan `FOUNDATION_SHA`.

```text
Anda adalah Anggota 4, pemilik API dan frontend Dashboard Analyzer.

ROOT REPOSITORY RESMI:
/Users/zoemohamed/project/Dashboard-Analyzer

BRANCH WAJIB:
team/4-frontend

Jangan bekerja dari /Users/zoemohamed/project/poc_python, .kilo/worktrees, atau
archive/legacy-poc.

LANGKAH WAJIB SEBELUM EDIT:
1. Verifikasi pwd, git status, branch, dan commit terakhir.
2. Branch harus team/4-frontend, working tree bersih, dan mengandung
   FOUNDATION_SHA integrator.
3. Baca penuh README.md, docs/SYSTEM.md, docs/FINAL_OUTPUT.md, docs/TEAM.md,
   app/contracts.py, app/config.py, dan app/main.py.
4. Jangan membuat bentuk response sendiri. Gunakan Snapshot/StreamEvent contract.

TUJUAN ANDA:
Membuat API tipis dan dashboard source-focused yang tetap menampilkan snapshot
lama saat refresh, menjelaskan progress/error, dan tidak membocorkan secret.

OWNERSHIP EKSKLUSIF:
- app/api/__init__.py
- app/api/dependencies.py
- app/api/health.py jika integrator mendelegasikan setelah fondasi
- app/api/topics.py
- app/api/snapshot.py
- app/api/refresh.py
- app/api/stream.py
- web/**
- tests/api/**
- tests/e2e/**

JANGAN EDIT:
- app/contracts.py, app/config.py, app/main.py tanpa permintaan integrator
- app/database/**, app/services/**, app/sources/**, app/intelligence/**
- migrations/**, requirements.txt, railway.json, atau dokumentasi

Jika backend service belum tersedia, gunakan fake service/dependency fixture yang
memenuhi contracts. Jangan menanam sample data ke production route/frontend.

API YANG HARUS DISEDIAKAN:
- GET /api/health (gunakan yang dibuat integrator; jangan duplikasi route)
- GET /api/topics
- POST /api/topics
- DELETE /api/topics/{topic_id}
- GET /api/topics/{topic_id}/snapshot
- POST /api/topics/{topic_id}/refresh
- GET /api/stream

ATURAN API:
- Route hanya validasi HTTP dan memanggil service/repository interface.
- Tidak ada SQL, Apify, Gemini, atau algoritma sentiment di route.
- Error body aman dan konsisten.
- Refresh tidak menggantung menunggu polling provider panjang.
- SSE memiliki ping, bounded queue behavior, dan JSON event sesuai contract.

UI FINAL:
- Header, product selector, add topic, refresh action, timestamp.
- Sidebar: Ringkasan, TikTok, Instagram, Facebook, Google Maps, Shopee,
  YouTube dalam urutan tersebut.
- Summary positif/negatif/netral/pending dan evidence count.
- Source status: never-run, queued, running, fresh, empty, stale,
  misconfigured, budget_exhausted, error.
- Evidence list dengan source, title/author, text, metrics, sentiment, timestamp,
  dan link Buka sumber.
- Snapshot lama tidak dikosongkan saat refresh.
- Debounce SSE agar event burst tidak memicu request snapshot berulang.
- UI desktop dan mobile 390px tanpa horizontal overflow.
- Semua dynamic text di-escape; external link memakai rel yang aman.
- Browser tidak membaca provider/database credential.

DESAIN:
- Gunakan visual direction clean market-intelligence yang konsisten dengan
  FINAL_OUTPUT.md.
- Source sidebar harus menjadi navigasi utama, bukan seluruh data dalam satu
  halaman panjang tanpa pemisahan.
- Empty/loading/error harus informatif, bukan ruang putih kosong.
- Jangan menambah framework frontend besar tanpa persetujuan integrator.

TEST WAJIB:
- Topic CRUD route dan validation.
- Snapshot route sukses/not found.
- Refresh route tidak memblokir.
- SSE encoding/event minimal.
- Source navigation memfilter evidence.
- Snapshot tetap terlihat pada state running.
- empty, misconfigured, budget exhausted, dan error memiliki copy berbeda.
- 390px tidak overflow horizontal.
- Tidak ada console error pada alur utama.

HANDOFF:
1. Jalankan tests/api dan tests/e2e yang tersedia.
2. Lakukan browser smoke test desktop dan mobile jika tooling tersedia.
3. Jalankan git diff --check dan audit ownership.
4. Commit dengan prefix feat(api), feat(web), test(api), test(e2e), atau fix(web).
5. Push hanya team/4-frontend; jangan merge main.

FORMAT LAPORAN AKHIR:
- Outcome
- Branch dan commit SHA
- Endpoint/UI state yang selesai
- Screenshot/viewport yang diverifikasi jika ada
- Command test dan hasil
- Service interface yang dibutuhkan dari Anggota 2
- Deviasi/limitasi desain
- Blocker

Mulai dengan audit read-only dan pembacaan penuh empat dokumen.
```

### Setelah prompt pertama

Jangan memberi prompt lanjutan yang berbunyi “selesaikan seluruh aplikasi”.
Berikan task kecil berdasarkan laporan agent, misalnya memperbaiki satu parser,
menambah satu migration, menguji satu edge case sentimen, atau menghubungkan satu
endpoint. Integrator menjaga contract dan urutan merge.

## 13. Handoff deployment kepada integrator

Setiap anggota memberikan informasi berikut sebelum release:

### Anggota 1

- Daftar provider dan actor/API yang benar-benar digunakan.
- Nama variable yang dibutuhkan tanpa nilainya.
- Timeout, limit, dan estimasi penggunaan per refresh.
- Bukti parser fixture dan satu live smoke test terbatas.

### Anggota 2

- Daftar migration dalam urutan eksekusi.
- Cara verifikasi schema dan rollback non-destruktif.
- Connection/pool configuration yang diperlukan.
- Bukti persistence setelah restart.

### Anggota 3

- Mode analyzer production dan fallback.
- Nama variable Gemini tanpa nilainya.
- Batas batch/rate yang aman.
- Bukti fallback saat Gemini tidak tersedia.

### Anggota 4

- Daftar endpoint yang digunakan frontend.
- Bukti UI menangani `misconfigured`, `empty`, dan `error`.
- Hasil desktop/mobile smoke test.
- Tidak ada secret atau direct provider URL pada bundle/browser.

### Checklist integrator di Railway

```text
[ ] main sinkron dan seluruh test lulus
[ ] railway.json sesuai app.main:app
[ ] healthcheckPath adalah /api/health
[ ] domain publik dibuat
[ ] APP_ENV=production
[ ] DATABASE_URL tersedia dan koneksi berhasil
[ ] APIFY_TOKEN/GEMINI_API_KEYS/REFRESH_TOKEN disimpan sebagai secret
[ ] migration production selesai
[ ] health HTTP 200
[ ] snapshot cache dapat dibaca
[ ] satu refresh terbatas berhasil atau status misconfigured tampil benar
[ ] build/deploy log tidak membocorkan credential
[ ] rollback target diketahui
```
