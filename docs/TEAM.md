# Team Workflow — 4 Orang

Dokumen ini mengatur pekerjaan paralel empat anggota selama clean rebuild.
Setiap anggota wajib membaca `README.md` dan `docs/SYSTEM.md` sebelum dokumen
ini.

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

## 4. Anggota 2 — Platform, database, dan orchestration

### Tujuan

Menyediakan database persisten, pipeline idempotent, usage budget, dan status
run yang dapat dibaca API.

### Ownership

```text
app/database/__init__.py
app/database/connection.py
app/database/repository.py
app/services/pipeline.py
app/services/usage.py
app/config.py
migrations/
tests/database/
tests/services/
```

### Output wajib

- Schema untuk topic, evidence, analysis, source run, metrics, dan usage.
- Unique constraint untuk deduplikasi evidence.
- Repository tanpa SQL di route.
- Refresh lock per topic/source.
- Snapshot-first dan stale refresh.
- Transaction pada perubahan status dan data penting.
- Migration aman untuk PostgreSQL/Supabase.

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

## 7. File milik integrator

Hanya integrator yang mengubah:

```text
app/contracts.py
app/main.py
requirements.txt
.env.example
railway.json atau Dockerfile
README.md
docs/SYSTEM.md
docs/TEAM.md
```

Integrator bertanggung jawab atas:

- Menetapkan kontrak sebelum pekerjaan paralel.
- Menggabungkan pull request sesuai dependency.
- Menjalankan seluruh test setelah setiap merge.
- Memastikan environment lokal dan Railway memakai konfigurasi yang sama.
- Menjaga maksimal tiga dokumen Markdown utama ini.
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

- Semua membaca tiga dokumen.
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

## 12. Cara memberi konteks kepada AI

Setiap anggota membuka AI dari root repo dan memberikan instruksi:

```text
Baca README.md, docs/SYSTEM.md, dan docs/TEAM.md sepenuhnya.
Saya adalah anggota N dan hanya memiliki ownership file yang tercantum untuk
anggota N. Jangan edit app/contracts.py atau app/main.py. Implementasikan output
wajib dan test minimum untuk peran saya. Jangan gunakan branch legacy sebagai
fondasi.
```

Setelah AI membaca dokumen, berikan task kecil dan terukur. Jangan meminta AI
“membangun seluruh aplikasi” dari branch anggota karena itu akan melanggar
ownership dan menghasilkan konflik besar.

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
