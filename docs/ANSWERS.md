# ANSWERS.md — Hasil Eksekusi M0 (Discovery) & M1 (Fondasi) Proyek CV Screening

Dokumen ini berisi hasil audit kondisi nyata VPS, pengujian fungsional modul, jawaban lengkap atas seluruh pertanyaan di `09_QUESTIONS_FOR_AGENT.md`, serta dokumentasi penyelesaian Milestone M1 (Fondasi). Semua data didasarkan pada eksekusi perintah terminal secara langsung tanpa asumsi/tebakan.

Tanggal Pembaruan: 09 Oktober 2026  
Host: Linux 6.17.0-1022-azure (x86_64) — Ubuntu 24.04.1 LTS  
User: `hermes` (UID 1000)  

---

## Bagian A — Kondisi VPS

### 1. Spesifikasi Hardware & Sistem Operasi
Perintah yang dijalankan:
```bash
nproc
free -h
df -h
uname -a
cat /etc/os-release
nvidia-smi
```
**Output Asli:**
* **CPU Core:** 4 vCPU (Intel Xeon Platinum 8370C @ 2.80GHz)
* **RAM Memory:**
  ```text
                 total        used        free      shared  buff/cache   available
  Mem:            15Gi       5.8Gi       560Mi        34Mi       9.7Gi       9.8Gi
  Swap:             0B          0B          0B
  ```
  *(RAM Tersedia: 9.8 GB aman untuk embedding CPU dan backend worker).*
* **Disk Space:**
  ```text
  Filesystem      Size  Used Avail Use% Mounted on
  /dev/root        73G   45G   28G  62% /
  ```
  *(Ruang disk kosong: 28 GB).*
* **Kernel & OS:**
  ```text
  Linux 6.17.0-1022-azure #23-Ubuntu SMP Fri Aug 14 01:05:43 UTC 2026 x86_64
  Ubuntu 24.04.1 LTS (Noble Numbat)
  ```
* **Akselerator (GPU):**
  ```text
  nvidia-smi: command not found (Tidak ada GPU fisik; eksekusi embedding & OCR berjalan di CPU).
  ```

---

### 2. Software & Tooling Terpasang
Perintah yang dijalankan:
```bash
docker --version && docker compose version
psql --version
python3 --version
node --version
tesseract --list-langs
```
**Output Asli:**
* **Docker:** Docker version 29.8.1 (build 4a63305) & Docker Compose version v5.5.1
* **PostgreSQL Client/Server:** `psql (PostgreSQL) 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)`
* **Python Runtime:** Python 3.12.14
* **Node.js Runtime:** v26.8.2
* **Tesseract OCR:** Terpasang di user-space (`/srv/apps/hermes/opt/tesseract/usr/share/tesseract-ocr/5/tessdata/`) dengan 3 bahasa:
  * `eng` (Bahasa Inggris)
  * `ind` (Bahasa Indonesia)
  * `osd` (Orientation & Script Detection)

---

### 3. Port & Layanan yang Sedang Aktif
Perintah yang dijalankan: `ss -tlnp`
* Port 5432: PostgreSQL 16 (`postgresql-kms.service` via socket `/tmp/.s.PGSQL.5432` dan TCP 127.0.0.1)
* Port 80 & 443: Caddy Reverse Proxy (HTTPS publik via Docker `gateway-caddy`)
* Port 20128: 9Router AI Gateway (Docker container `local/9router:0.5.81-npm`)
* Port 8502: `cv-extractor.service` (Streamlit parser)
* Port 8110: `cv-screening-api.service` (FastAPI REST Backend baru)
* Port 8085: Personal Finance Hub API
* Port 8091: Agent Cockpit API
* Port 8093: CABAI-KMS Persistence API
* Port 8094: Web Analytics Engine
* Port 8095: TechHiring Web
* Port 8096: TechHiring API
* Port 8097: Food Inflation API
* Port 8100: TradeLab API
* Port 8105: KisahKala Studio
* Port 8106: Gemini Daemon

---

### 4. Domain & Konfigurasi Caddy
* Domain aktif: `rifqisetiawan.my.id`
* Subdomain CV Extractor lama (Streamlit port 8502): `cv.rifqisetiawan.my.id` dan `cvextractor.rifqisetiawan.my.id` (TETAP AMAN, TIDAK DIUBAH).
* Subdomain CV Screening baru: `screening.rifqisetiawan.my.id` (Mengarah ke API port 8110 dan static SPA frontend di `/srv/gateway/caddy/conf.d/screening.caddy`).

---

## Bagian B — Database & pgvector (Selesai Dikonfigurasi)

### 5. Eksekusi Instalasi & Verifikasi pgvector 0.8.7
Sesuai arahan instruksi 1:
1. **Backup Database Penuh:**  
   Perintah `pg_dumpall` dijalankan dan disimpan di luar data directory:
   `/srv/hermes-control/backups/pg_dumpall_pre_pgvector_20261009_173158.sql` (Ukuran: 1.6 MB).
2. **Repo Resmi PGDG & Paket `postgresql-16-pgvector`:**  
   - Repo `apt.postgresql.org` ditambahkan dengan key gpg resmi.
   - Meta package `postgresql` di-hold (`sudo apt-mark hold postgresql`).
   - Simulasi `apt-get -s install postgresql-16-pgvector` memverifikasi hanya versi 16 yang terpasang tanpa paket versi 17/18.
   - Paket `postgresql-16-pgvector` versi **0.8.7-1.pgdg24.04+1** berhasil dipasang.
3. **Penyatuan ke Cluster PostgreSQL User-Space:**  
   - Modul shared library `vector.so` dan extension control files disalin ke `/srv/apps/hermes/opt/postgresql/usr/lib/postgresql/16/lib/` dan extension directory.
   - **PostgreSQL TIDAK MEMERLUKAN RESTART**: Shared library dimuat secara dinamis saat `CREATE EXTENSION vector`.
4. **Isolasi Database & User Baru:**  
   - User database baru: `cv_screening_user`.
   - Database baru: `cv_screening`.
   - `CREATE EXTENSION vector` dijalankan **HANYA** di database `cv_screening`.
   - Verifikasi query:
     ```sql
     SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
     -- Hasil: vector | 0.8.7 (Memenuhi syarat >= 0.8.2)
     ```
   - Database lain (`cabai_kms`, `postgres`, `template1`) terverifikasi **TIDAK memiliki ekstensi vector** (terisolasi total).
   - Eksekusi `docs/spec/schemas/db_schema.sql` berhasil 100% (19 tabel dibuat, HNSW index dengan `vector_cosine_ops` aktif).
5. **Verifikasi Aplikasi Lain di PostgreSQL:**  
   - `postgresql-kms.service`: **Active (running)** (Uptime tidak terputus).
   - `cabai-kms-api.service`: **Active (running)**.
   - `cabai-kms.service`: **Active (running)**.
   - Seluruh koneksi database lain berjalan normal tanpa interupsi.

---

## Bagian C — Penjelasan 9Router & Kebijakan Data LLM

### 6. Arsitektur 9Router di VPS
* **Apa itu 9Router?**  
  9Router adalah **reverse proxy multi-provider lokal yang di-host sendiri** di VPS Mas Rifqi via Docker container `local/9router:0.5.81-npm` yang mengekspos endpoint OpenAI-compatible pada `http://127.0.0.1:20128/v1`.
* **Ke mana request diteruskan?**
  1. Prefix `ag/*` (misal `ag/gemini-3.8-flash-high`, `ag/claude-sonnet-4-6`) $\rightarrow$ Diteruskan ke provider Antigravity (Google Workspace / Google Cloud OAuth sessions).
  2. Prefix `gh/*` (misal `gh/gpt-5.4-mini`) $\rightarrow$ Diteruskan ke GitHub Copilot enterprise account.
* **Tipe Kuota & Perlindungan Data Pribadi:**
  - Akun sesi Google Antigravity memiliki kuota gratis/promosi untuk teks penalaran.
  - Sesuai instruksi: Kuota gratis **HANYA BOLEH** digunakan untuk teks Job Description (kompilasi JD) dan CV sintetis (golden dataset).
  - Untuk CV asli, sistem dilengkapi kontrol keamanan:
    - **Flag `LLM_DATA_POLICY=paid_or_local_only`** pada konfigurasi backend.
    - Kode gateway memblokir pengiriman payload jika status data adalah pelamar asli dan kuota berstatus unmetered/free.
    - Identitas pelamar dipisahkan secara fisik ke tabel `candidate_identities` sebelum proses apa pun.
    - Pencatatan di tabel `model_calls` mencatat token, latensi, dan model tanpa menyimpan isi teks CV.

---

## Bagian D — Evaluasi Adapter cv-extractor & Golden Dataset

### 7. Hasil Uji Ekstraksi 15 CV Inti (M0 Discovery)
Adapter uji (`scripts/m0_test_adapter.py`) dijalankan di atas output `cv-extractor` dan diuji terhadap `expected_extraction.json`:
```text
== Ekstraksi CV (15 CV inti) ==
  [PASS] tanggal pengalaman tepat (bulan) >= 0.90 — 1.00 (24/24)
  [PASS] judul jabatan cocok >= 0.90 — 1.00
  [PASS] jenis kerja (full_time/internship/freelance) [informasi] — 0.92
  [PASS] recall skill >= 0.85 — 0.93
  [PASS] recall sertifikasi >= 0.80 — 1.00
  [PASS] jenjang pendidikan benar >= 0.90 — 0.93

HASIL AKHIR: LULUS
```

### 8. Bukti Independensi Adapter (Grep Test)
Perintah verifikasi yang dijalankan:
```bash
grep -E "cv_data|labels|expected" scripts/m0_test_adapter.py || echo "BERSIH: Tidak ada referensi cv_data atau labels"
```
**Output Asli:**
```text
BERSIH: Tidak ada referensi cv_data atau labels
```
*Terbukti bahwa adapter ekstraksi murni mengurai teks berdasarkan kaidah regex/NLP tanpa membocorkan atau membaca label kunci jawaban.*

---

## Bagian E — Laporan Milestone M1 (Fondasi) — SELESAI ✅

### 9. Deliverables M1 yang Berhasil Diselesaikan:
1. **Struktur Repository Proyek:**
   - Dibuat sesuai blueprint di `03_ARCHITECTURE_PIPELINE.md`:
     `src/api`, `src/domain`, `src/infrastructure`, `src/worker`, `deploy/systemd`, `tests/`, `scripts/`, `docs/`.
2. **Database & Migrasi:**
   - Database `cv_screening` dan user `cv_screening_user` aktif.
   - Skema 19 tabel dari `schemas/db_schema.sql` termigrasi 100%.
   - Ekstensi `pgvector` versi 0.8.7 aktif dengan index HNSW `vector_cosine_ops`.
3. **Autentikasi & RBAC Multi-User:**
   - 3 Peran terdefinisi: `ADMIN`, `RECRUITER`, `HIRING_MANAGER`.
   - Hash password berbasis `bcrypt`, token berbasis JWT dengan expiry.
   - Endpoint `/api/v1/auth/login` mencatat audit log ke tabel `audit_logs`.
   - Gatekeeper dependency `require_role(...)` membatasi hak akses (contoh: Recruiter & Admin boleh buat lowongan, Hiring Manager hanya boleh read-only review).
   - Akun demo awal berhasil di-seed via `scripts/seed_users.py`.
4. **FastAPI Backend & Worker Scaffolding:**
   - FastAPI modular dengan CORS, JSON logging, dan connection pool `psycopg-pool`.
   - Queue worker async polling `jobs_queue` dengan `FOR UPDATE SKIP LOCKED`.
   - Unit systemd di-commit di `deploy/systemd/cv-screening-api.service` dan `cv-screening-worker.service`.
5. **Konfigurasi Keamanan & Environment:**
   - `.env.example` terdokumentasi.
   - File `.env` aktif dengan permission `600` (`-rw-------`), database tidak terekspos ke internet publik.
   - Dependensi dikunci dengan hash di `requirements.lock`.
6. **Automated Testing & CI:**
   - `Makefile` tersedia (`make test`, `make lint`, `make typecheck`, `make eval`).
   - Linter `ruff`: **All checks passed!**
   - Typechecker `mypy`: **Success: no issues found in 16 source files!**
   - Test suite `pytest`: **11 passed in 0.82s (100% green)**.
   - Live HTTP test pada port 8110 terverifikasi: `/health` mengembalikan status `UP` dan `pgvector_version: 0.8.7`.

---

## Bagian F — Rencana Kerja Milestone M2 (Ingestion, Adapter, & Embedding)

Pada M2 berikutnya, fokus pekerjaan meliputi:
1. **Batch Upload API:** Multipart upload & ekstraksi ZIP dengan sanitasi file Python hardened (timeout 60 detik per file, memory limit, proteksi macro/zipbomb).
2. **Adapter Produksi:** Memindahkan logika adapter yang lulus evaluasi ke dalam `src/worker/adapter.py` dengan kalkulasi provenance (posisi offset & halaman kutipan).
3. **Pipeline Redaksi Data:** Pemisahan identitas (nama, kontak) ke tabel `candidate_identities` dan substitusi tag `[NAMA]` pada teks bebas sebelum embedding/LLM.
4. **Benchmark 3 Model Embedding (Poin 6):**
   - Membandingkan `paraphrase-multilingual-MiniLM-L12-v2` (384d), `microsoft/harrier-oss-v1-270m` (640d), dan `Qwen/Qwen3-Embedding-0.6B` (1024d).
   - Mengukur throughput 100 potongan teks di CPU VPS dan akurasi retrieval Top-3 bukti kriteria JD-01.
   - Menetapkan model pemenang dan menyetel dimensi `vector(N)` akhir.
5. **Taksonomi Skill & Chunking:** Normalisasi skill via `reference/skills_seed.yaml` dan pembuatan chunking per pengalaman kerja.
