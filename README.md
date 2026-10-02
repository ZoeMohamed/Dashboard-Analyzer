# POC Scrapper

POC Scrapper adalah dashboard pemantauan tren dan opini produk UMKM Indonesia.
Aplikasi mengumpulkan bukti publik dari beberapa sumber, menyaring data yang
relevan dengan produk, menganalisis sentimen Bahasa Indonesia, lalu menyajikan
hasil yang dapat ditelusuri kembali ke URL sumber.

Repositori ini adalah **clean rebuild**. Jangan menyalin struktur aplikasi lama
secara utuh. Branch `archive/legacy-poc` hanya boleh digunakan sebagai referensi
perilaku fitur ketika benar-benar diperlukan.

## Dokumen wajib

Setiap anggota tim dan AI coding assistant harus membaca dokumen berikut secara
berurutan sebelum menulis kode:

1. `README.md` — tujuan, scope, setup, dan aturan umum.
2. `docs/SYSTEM.md` — arsitektur, kontrak data, pipeline, dan API.
3. `docs/TEAM.md` — pembagian kerja, ownership file, Git, dan jadwal integrasi.

Jika implementasi bertentangan dengan dokumen, hentikan perubahan dan selaraskan
dokumen bersama tim terlebih dahulu.

## Scope POC

Sumber produksi yang direncanakan:

- TikTok: post/video publik dan metrik yang tersedia.
- Instagram: caption/post publik dan metrik yang tersedia.
- Facebook: post publik dan metrik yang tersedia.
- Google Maps: tempat dan ulasan yang menyebut produk.
- Shopee: listing produk, harga, rating, dan jumlah terjual jika tersedia.
- YouTube: video tren yang relevan dengan produk UMKM.

Fitur inti:

- Pengguna dapat membuat topik produk apa pun, bukan hanya data seed.
- Setiap sumber memiliki status proses dan error yang terpisah.
- Data tersimpan ditampilkan terlebih dahulu sebelum refresh berjalan.
- Evidence selalu menyimpan sumber, ID eksternal, URL, dan waktu koleksi.
- Filter relevansi mencegah konten hiburan yang hanya kebetulan menyebut kata
  produk.
- Sentimen memahami konteks Bahasa Indonesia dan memiliki fallback lokal.
- API key hanya digunakan backend dan tidak pernah dikirim ke browser.

Di luar scope POC:

- Login pengguna dan sistem pembayaran.
- Scraping akun privat atau data yang membutuhkan bypass autentikasi.
- Klaim bahwa semua data internet berhasil dikumpulkan.
- Prediksi bisnis yang tidak memiliki evidence.

## Target teknologi

- Python 3.11+
- FastAPI dan Uvicorn
- PostgreSQL/Supabase untuk data persisten
- Apify untuk provider yang memerlukannya
- Gemini opsional untuk klasifikasi kontekstual
- HTML, CSS, dan JavaScript modular untuk dashboard POC
- Pytest untuk pengujian
- Railway untuk deployment backend

Dependency final dipilih oleh pemilik platform dan dicatat di file dependency
yang dikunci versinya. Jangan menambahkan framework kedua untuk fungsi yang sama.

## Struktur target

```text
POC_Scrapper/
├── app/
│   ├── api/                 # HTTP routes dan dependency wiring
│   ├── database/            # koneksi, repository, dan migration helpers
│   ├── intelligence/        # relevansi, normalisasi, dan sentimen
│   ├── sources/             # adapter setiap sumber
│   ├── contracts.py         # kontrak data lintas modul
│   ├── config.py            # environment configuration
│   └── main.py              # FastAPI entrypoint
├── migrations/              # perubahan schema PostgreSQL
├── tests/                   # unit, integration, dan contract tests
├── web/                     # dashboard
├── docs/
│   ├── SYSTEM.md
│   └── TEAM.md
├── .env.example             # nama variabel tanpa secret
├── README.md
└── requirements.txt
```

Struktur boleh bertambah jika ada kebutuhan nyata, tetapi ownership pada
`docs/TEAM.md` tetap berlaku.

## Setup lokal

Perintah ini berlaku setelah fondasi aplikasi dibuat:

```bash
cd "/Users/zoemohamed/project/POC_Scrapper"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
PYTHONPATH=. pytest -q
PYTHONPATH=. uvicorn app.main:app --reload
```

Alamat lokal yang direncanakan:

- Dashboard: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/api/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

## Environment variable

Nama minimal yang direncanakan:

```text
APP_ENV
DATABASE_URL
APIFY_TOKEN
GEMINI_API_KEYS
REFRESH_TOKEN
```

Nilai sebenarnya hanya boleh berada di `.env`, Supabase, atau Railway Variables.
Jangan commit `.env`. Credential yang pernah dibagikan melalui chat harus
dirotasi sebelum deployment final.

## Railway

Start command yang akan dipakai:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Railway menerima traffic hanya setelah `/api/health` berhasil. Database wajib
menggunakan PostgreSQL/Supabase; jangan mengandalkan SQLite di filesystem
deployment.

## Definition of done

Rebuild dinyatakan selesai apabila:

- Topik baru dapat dibuat dan tetap ada setelah restart.
- Keenam sumber menggunakan kontrak evidence yang sama.
- Satu provider gagal tanpa menjatuhkan provider lain.
- Snapshot lama tetap tampil ketika refresh berlangsung.
- Status `queued`, `running`, `fresh`, `empty`, `misconfigured`,
  `budget_exhausted`, dan `error` terlihat jelas.
- Filter hanya menyimpan evidence yang relevan dengan produk UMKM.
- Sentimen Indonesia memiliki pengujian untuk negasi dan kalimat retoris.
- Tidak ada data demo yang dilabel sebagai data live.
- Secret tidak muncul di repository, response API, log, atau browser.
- Seluruh test lulus dan deployment Railway health check berhasil.

## Aturan utama

- Kerjakan hanya pada repo `POC_Scrapper`, bukan `poc_python`.
- Jangan mengubah kontrak lintas tim tanpa persetujuan integrator.
- Jangan melakukan force-push ke `main` setelah pekerjaan tim dimulai.
- Jangan menambahkan seed palsu ke jalur produksi.
- Setiap pull request harus kecil, dapat diuji, dan sesuai ownership file.
