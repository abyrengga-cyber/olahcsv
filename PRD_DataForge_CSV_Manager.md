# PRD — DataForge: CSV & TXT File Processing Web Application

**Versi:** 1.0  
**Tanggal:** April 2026  
**Status:** Draft  
**Platform:** Django Web Application  

---

## 1. Ringkasan Eksekutif

DataForge adalah aplikasi web berbasis Django yang dirancang untuk memudahkan pengolahan file CSV dan TXT dari berbagai sumber dengan format yang tidak seragam. Aplikasi ini memungkinkan pengguna mengunggah, membersihkan, menstandarisasi, memvisualisasikan, dan mengekspor data ke format CSV atau XLSX dengan antarmuka GUI yang intuitif dan efisien.

**Permasalahan yang diselesaikan:**
- File CSV/TXT dari berbagai sumber memiliki delimiter berbeda (koma, tab, spasi, pipa)
- Kolom waktu (date, time) sering terpisah dan tidak seragam formatnya
- Proses seleksi kolom untuk ekspor dilakukan manual dan berulang
- Tidak ada alat terpadu untuk agregasi, perbandingan persentase, dan visualisasi data

---

## 2. Tujuan Produk

### 2.1 Tujuan Utama
- Menyederhanakan proses pengolahan file CSV/TXT menjadi format bersih yang siap digunakan
- Menghemat waktu kerja repetitif melalui fitur Preset
- Menyediakan insight data dasar (agregasi, perbandingan, visualisasi) langsung dalam satu platform

### 2.2 Metrik Keberhasilan
- Waktu proses dari upload hingga export < 60 detik untuk file < 10MB
- Tingkat akurasi deteksi otomatis format tanggal > 95%
- Pengguna dapat menyimpan dan menggunakan kembali preset dalam < 3 klik

---

## 3. Target Pengguna

| Persona | Deskripsi | Kebutuhan Utama |
|---|---|---|
| Analis Data | Bekerja rutin dengan laporan dari berbagai sistem | Ekspor cepat, preset, normalisasi waktu |
| Staff Operasional | Mengolah laporan mesin/sensor | Gabung multi-file, deteksi kolom kosong |
| Finance/Accounting | Rekonsiliasi data dari sistem berbeda | Penjumlahan total, perbandingan persentase |
| Data Engineer | Preprocessing pipeline data | Batch processing, format fleksibel |

---

## 4. Fitur dan Spesifikasi Fungsional

### 4.1 Upload & Parsing File

**Deskripsi:** Pengguna dapat mengunggah satu atau beberapa file sekaligus. Sistem secara otomatis mendeteksi format dan delimiter.

**Spesifikasi:**
- Format yang didukung: `.csv`, `.txt`
- Ukuran maksimum file: 50MB per file, 200MB total per sesi
- Jumlah file per upload: maks 20 file
- Delimiter yang terdeteksi otomatis: koma (`,`), titik koma (`;`), tab (`\t`), pipa (`|`), spasi tunggal/multipel
- Encoding yang didukung: UTF-8, UTF-16, Latin-1, Windows-1252 (auto-detect)
- Preview otomatis 20 baris pertama setelah upload berhasil

**Alur:**
1. Pengguna drag-and-drop atau browse file
2. Sistem parsing header dan sample baris
3. Sistem menampilkan preview tabel dengan info: jumlah baris, kolom, delimiter terdeteksi, encoding
4. Pengguna dapat mengoreksi delimiter dan encoding jika deteksi salah

**Validasi:**
- Notifikasi jika file kosong atau tidak dapat dibaca
- Notifikasi jika header duplikat ditemukan dalam satu file
- Notifikasi jika kolom memiliki nilai kosong/null > 50%

---

### 4.2 GUI Seleksi Kolom

**Deskripsi:** Antarmuka visual untuk memilih kolom mana saja yang akan diikutsertakan dalam ekspor, baik dari satu file maupun kombinasi beberapa file.

**Spesifikasi:**
- Tampilan daftar kolom per file dengan checkbox untuk memilih/tidak memilih
- Drag-and-drop untuk mengatur urutan kolom dalam output
- Kemampuan rename kolom sebelum ekspor (alias kolom)
- Indikator visual jika kolom mengandung data kosong (warna kuning/ikon peringatan)
- Indikator visual jika kolom bertipe numerik, teks, atau waktu
- Mode "Select All" dan "Deselect All" per file

**Multi-file Column Mapping:**
- Ketika beberapa file dipilih, sistem menampilkan kolom dari masing-masing file secara terpisah
- Pengguna dapat menamai kolom dari file berbeda menjadi nama kolom yang sama di output (merge by name)
- Sistem menampilkan preview kolom gabungan sebelum ekspor

---

### 4.3 Normalisasi Kolom Waktu (DATETIME)

**Deskripsi:** Sistem secara otomatis mendeteksi dan menggabungkan kolom tanggal dan waktu yang terpisah, serta menstandarisasi format ke satu kolom DATETIME yang seragam.

**Format yang dideteksi dan dikonversi:**
- `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY-MM-DD`, `DD-MM-YYYY`
- `HH:MM:SS`, `HH:MM`, `HH:MM:SS.mmm` (dengan milidetik)
- Unix timestamp (integer detik dan milidetik)
- Format ISO 8601: `2024-01-15T08:30:00Z`
- Kombinasi kolom Date + Time terpisah

**Spesifikasi:**
- Deteksi otomatis kolom yang kemungkinan berisi tanggal atau waktu berdasarkan nama kolom (mengandung kata: date, time, datetime, timestamp, tgl, jam, waktu) dan sampling nilai
- Konfirmasi dari pengguna sebelum penggabungan: sistem menampilkan dialog yang menunjukkan kolom mana yang akan digabung dan format output yang dipilih
- Format output DATETIME yang tersedia: `YYYY-MM-DD HH:MM:SS`, `DD/MM/YYYY HH:MM:SS`, ISO 8601, Unix timestamp
- Kolom date dan time asli dapat dipertahankan atau dihapus sesuai pilihan pengguna
- Jika format tanggal ambigu (contoh: 01/02/2024 bisa DD/MM atau MM/DD), sistem meminta konfirmasi dari pengguna dengan menampilkan contoh nilai

**Notifikasi:**
- Peringatan jika ada baris dengan nilai tanggal/waktu yang tidak dapat diparse
- Laporan jumlah baris yang berhasil dikonversi vs gagal

---

### 4.4 Deteksi dan Pelaporan Kolom Kosong

**Deskripsi:** Sistem mengidentifikasi dan melaporkan kolom dengan nilai kosong/null/missing.

**Spesifikasi:**
- Analisis dilakukan otomatis setelah parsing file
- Panel "Data Quality Report" menampilkan:
  - Nama kolom
  - Persentase nilai kosong
  - Jumlah baris kosong vs total baris
  - Indikator severity: hijau (0%), kuning (1–20%), merah (>20%)
- Opsi filter: tampilkan hanya baris yang lengkap, atau biarkan semua baris
- Opsi isi nilai kosong: biarkan kosong, isi dengan "N/A", isi dengan nilai sebelumnya (forward fill), atau isi dengan nilai rata-rata (untuk kolom numerik)

---

### 4.5 Agregasi: Penjumlahan Total

**Deskripsi:** Pengguna dapat memilih kolom numerik untuk dijumlahkan dan menampilkan baris total di bagian bawah output.

**Spesifikasi:**
- Pilih satu atau beberapa kolom numerik untuk disertakan dalam perhitungan total
- Jenis agregasi yang tersedia: SUM, AVERAGE, MIN, MAX, COUNT
- Hasil agregasi ditampilkan sebagai baris tambahan di bagian bawah tabel
- Baris total dapat diikutsertakan dalam file ekspor sebagai baris terakhir
- Jika terdapat kolom grup (contoh: category, region), tersedia opsi GROUP BY untuk menghitung subtotal per grup

---

### 4.6 Perbandingan Persentase Dua Kolom

**Deskripsi:** Pengguna dapat membandingkan dua kolom numerik dan menampilkan kolom persentase perbedaan atau rasio.

**Spesifikasi:**
- UI: dropdown pilih Kolom A dan Kolom B
- Jenis kalkulasi yang tersedia:
  - Persentase selisih: `((A - B) / B) × 100%`
  - Rasio: `A / B`
  - Persentase kontribusi: `(A / Total A) × 100%`
- Hasil disimpan sebagai kolom baru dengan nama yang dapat dikustomisasi
- Kolom hasil dapat diikutsertakan dalam ekspor
- Format tampilan persentase: 2 desimal, disertai simbol `%`

---

### 4.7 Visualisasi Data (Grafik Batang dan Pie)

**Deskripsi:** Pengguna dapat membuat visualisasi sederhana dari data yang telah diolah langsung di dalam aplikasi.

**Spesifikasi:**

**Grafik Batang (Bar Chart):**
- Pilih kolom X (kategori/label) dan kolom Y (nilai numerik)
- Mendukung multi-series (lebih dari satu kolom Y)
- Opsi tampilan: vertikal, horizontal
- Opsi filter: tampilkan top-N, filter berdasarkan nilai minimum

**Grafik Pie:**
- Pilih satu kolom kategori dan satu kolom nilai
- Otomatis menghitung persentase setiap segmen
- Opsi: gabungkan kategori kecil (<X%) menjadi "Lainnya"

**Umum:**
- Library: Chart.js (dirender di browser, ringan)
- Warna otomatis dengan palet yang dapat dikustomisasi
- Tombol download grafik sebagai PNG atau SVG
- Grafik diperbarui real-time saat kolom yang dipilih berubah

---

### 4.8 Ekspor File

**Deskripsi:** Pengguna dapat mengekspor data hasil pengolahan ke format CSV sederhana atau XLSX.

**Spesifikasi:**

**Ekspor CSV:**
- Delimiter output: koma, titik koma, atau tab (pilihan pengguna)
- Encoding output: UTF-8, UTF-8 with BOM (untuk kompatibilitas Excel)
- Opsi header: sertakan atau tidak sertakan baris header

**Ekspor XLSX:**
- Sheet tunggal atau multi-sheet (jika berasal dari multi-file)
- Baris header dengan format bold dan background warna
- Kolom total (jika ada) ditandai dengan background kuning muda
- Kolom DATETIME otomatis diformat sebagai tipe Date di Excel
- Kolom persentase diformat sebagai format Percentage di Excel
- Lebar kolom auto-fit berdasarkan isi data

**Gabungan Multi-file:**
- Pengguna dapat memilih beberapa file dan kolom dari masing-masing file
- Output digabungkan secara vertikal (row-append) dengan header yang terstandarisasi
- Kolom yang tidak ada di semua file diisi kosong

---

### 4.9 Sistem Preset

**Deskripsi:** Pengguna dapat menyimpan konfigurasi pengolahan data (pilihan kolom, normalisasi waktu, format ekspor) sebagai preset untuk digunakan kembali.

**Spesifikasi:**

**Penyimpanan Preset:**
- Nama preset (maks 50 karakter)
- Deskripsi opsional
- Konfigurasi yang disimpan: kolom yang dipilih, urutan kolom, alias kolom, format DATETIME, setting agregasi, setting perbandingan persentase, format ekspor (CSV/XLSX)
- Preset dikaitkan dengan "tipe file" berdasarkan nama file atau pola header kolom

**Penggunaan Preset:**
- Setelah upload file, sistem secara otomatis menyarankan preset yang relevan berdasarkan kesamaan nama kolom
- Pengguna dapat memilih dan menerapkan preset dengan satu klik
- Preset dapat diedit, diduplikasi, dan dihapus

**Penyimpanan:**
- Preset disimpan di database server (bukan hanya browser)
- Pengguna yang login dapat mengakses preset mereka dari perangkat manapun

---

## 5. Arsitektur Teknis

### 5.1 Stack Teknologi

**Backend:**
- Framework: Django 5.x (Python 3.12+)
- REST API: Django REST Framework (DRF)
- Task Queue: Celery + Redis (untuk file besar dan proses async)
- Database: PostgreSQL 16
- File Storage: Django FileField dengan local storage (dapat dikembangkan ke S3)
- Parsing Library: pandas, chardet (encoding detection), python-dateutil

**Frontend:**
- Template Engine: Django Templates + Jinja2
- CSS Framework: Tailwind CSS (via CDN atau compiled)
- JavaScript: Vanilla JS + Alpine.js (reaktivitas ringan)
- Grafik: Chart.js
- Drag-and-drop: Sortable.js
- File Upload: Dropzone.js atau filepond

**Export Library:**
- XLSX: openpyxl
- CSV: stdlib Python csv module

### 5.2 Struktur Aplikasi Django

```
dataforge/
├── config/               # Settings, URLs, WSGI/ASGI
├── apps/
│   ├── accounts/         # Autentikasi pengguna
│   ├── files/            # Upload, parsing, storage
│   ├── processor/        # Normalisasi, agregasi, perbandingan
│   ├── export/           # Generator CSV dan XLSX
│   ├── presets/          # Manajemen preset
│   └── charts/           # API data untuk visualisasi
├── static/               # CSS, JS, gambar
├── templates/            # HTML templates
└── media/                # File yang diupload (sementara)
```

### 5.3 Model Data Utama

**UploadedFile**
- id, user, original_filename, file_path, file_size, delimiter, encoding, row_count, column_count, upload_at, status

**ProcessingSession**
- id, user, files (M2M), configuration (JSON), created_at, status

**Preset**
- id, user, name, description, column_config (JSON), datetime_config (JSON), export_config (JSON), trigger_pattern (JSON), created_at, updated_at

**ExportJob**
- id, session, format (csv/xlsx), status, output_file, created_at, completed_at

### 5.4 Alur Data Utama

```
Upload File → Parsing & Detection → Preview
     ↓
Seleksi Kolom → Normalisasi DATETIME → Quality Check
     ↓
Agregasi / Perbandingan → Visualisasi
     ↓
Ekspor CSV / XLSX
```

---

## 6. Antarmuka Pengguna (UI/UX)

### 6.1 Halaman Utama / Dashboard
- Panel upload file (drag-and-drop area yang menonjol)
- Daftar file yang sudah diupload dalam sesi ini
- Shortcut: preset yang sering digunakan
- Riwayat ekspor terakhir

### 6.2 Workspace (Halaman Utama Pengolahan)
Layout tiga panel:

**Panel Kiri (File & Column Manager):**
- Tree view daftar file yang diupload
- Kolom dari setiap file dengan checkbox, tipe data, dan indikator kualitas
- Tombol "Add File" untuk menambah file ke sesi

**Panel Tengah (Preview Tabel):**
- Tabel preview data yang sudah diproses
- Sticky header
- Pagination (50 baris per halaman)
- Indikator kolom kosong dengan highlight

**Panel Kanan (Tools & Settings):**
- Tab: DATETIME, Agregasi, Perbandingan, Visualisasi
- Tombol Preset (simpan/muat)
- Tombol Ekspor

### 6.3 Responsivitas
- Desktop-first (lebar minimal 1024px untuk workspace penuh)
- Tablet: panel dapat dilipat/expanded
- Mobile: akses terbatas untuk review dan download saja

### 6.4 Notifikasi dan Feedback
- Toast notification untuk aksi berhasil/gagal
- Progress bar untuk file besar atau proses ekspor
- Tooltip informatif pada setiap ikon/tombol
- Dialog konfirmasi untuk aksi yang tidak dapat dibatalkan

---

## 7. Keamanan

- Autentikasi: Django built-in auth + session
- File upload: validasi MIME type, ukuran file, dan ekstensi
- File disimpan sementara: otomatis dihapus setelah 24 jam atau setelah sesi selesai
- CSRF protection: aktif pada semua form dan AJAX request
- Rate limiting: maksimum 10 upload per menit per pengguna
- Tidak ada eksekusi konten file: parsing hanya membaca data, bukan menjalankan formula/macro
- Isolasi data: pengguna hanya dapat mengakses file dan preset milik akun sendiri

---

## 8. Performa

| Kondisi | Target |
|---|---|
| File CSV < 1MB | Parsing < 2 detik |
| File CSV 1–10MB | Parsing < 10 detik |
| File CSV 10–50MB | Parsing < 60 detik (async via Celery) |
| Ekspor file < 10MB | < 5 detik |
| Preview tabel | < 1 detik (hanya 20–50 baris) |

Untuk file > 10MB, proses dilakukan secara asinkron dengan progress indicator dan notifikasi email opsional ketika selesai.

---

## 9. Batasan dan Asumsi

**Batasan Versi 1.0:**
- Tidak mendukung file Excel (.xlsx) sebagai input (hanya output)
- Tidak mendukung file JSON atau XML sebagai input
- Visualisasi tidak dapat diekspor sebagai bagian dari file XLSX
- Tidak ada fitur kolaborasi multi-pengguna pada satu sesi
- Tidak ada API publik (hanya UI)

**Asumsi:**
- Pengguna memiliki pemahaman dasar tentang struktur data tabel
- Satu sesi pengolahan dapat menampung maksimum 20 file
- Data bersifat non-sensitif (tidak ada enkripsi end-to-end data file)

---

## 10. Roadmap Pengembangan

### Fase 1 — MVP (Bulan 1–3)
- Upload dan parsing CSV/TXT
- Seleksi kolom dengan GUI
- Normalisasi DATETIME
- Deteksi kolom kosong
- Ekspor CSV dan XLSX
- Sistem Preset dasar
- Autentikasi pengguna

### Fase 2 — Fitur Lanjutan (Bulan 4–6)
- Agregasi dan perbandingan persentase
- Visualisasi grafik (Bar dan Pie)
- Multi-file merge
- Quality report lengkap
- Async processing untuk file besar

### Fase 3 — Optimasi (Bulan 7–9)
- Input dari Excel (.xlsx)
- Ekspor multi-sheet XLSX
- API endpoint dasar
- Template preset berbasis komunitas
- Dukungan filter baris (bukan hanya kolom)

---

## 11. Kriteria Penerimaan (Acceptance Criteria)

| Fitur | Kriteria Penerimaan |
|---|---|
| Upload File | Berhasil parse file CSV dan TXT dengan delimiter otomatis terdeteksi ≥ 5 format |
| Seleksi Kolom | Pengguna dapat memilih subset kolom dan hasilnya tercermin di preview sebelum ekspor |
| Normalisasi DATETIME | Minimal 8 format tanggal/waktu berbeda dikonversi ke satu format output pilihan pengguna |
| Kolom Kosong | Kolom dengan nilai kosong ditandai jelas dan pengguna diberi opsi penanganan |
| Agregasi | Baris SUM/AVG/MIN/MAX muncul di output dan dapat diikutsertakan dalam file ekspor |
| Perbandingan | Kolom persentase baru muncul di tabel dengan kalkulasi yang benar |
| Visualisasi | Grafik bar dan pie tampil sesuai kolom yang dipilih dan dapat diunduh sebagai PNG |
| Ekspor CSV | Output CSV valid, dapat dibuka di Excel dan text editor |
| Ekspor XLSX | Output XLSX valid dengan format header dan kolom yang sesuai spesifikasi |
| Preset | Preset dapat disimpan, dimuat, dan diterapkan dalam 3 klik atau kurang |

---

## 12. Lampiran

### 12.1 Contoh Format Waktu yang Didukung

| Format Input | Contoh Nilai | Keterangan |
|---|---|---|
| DD/MM/YYYY | 15/01/2024 | Format Indonesia umum |
| MM/DD/YYYY | 01/15/2024 | Format US |
| YYYY-MM-DD | 2024-01-15 | Format ISO 8601 tanggal |
| DD-MM-YYYY HH:MM:SS | 15-01-2024 08:30:00 | Tanggal + waktu dengan dash |
| ISO 8601 | 2024-01-15T08:30:00Z | Dengan timezone UTC |
| Unix Timestamp | 1705301400 | Detik sejak epoch |
| Kolom terpisah | date=15/01/2024, time=08:30 | Dua kolom digabung |

### 12.2 Contoh Konfigurasi Preset (JSON)

```json
{
  "name": "Laporan Sensor Mesin A",
  "trigger_pattern": {
    "header_keywords": ["timestamp", "temperature", "pressure", "machine_id"]
  },
  "column_config": [
    {"source_name": "timestamp", "alias": "DATETIME", "include": true, "order": 1},
    {"source_name": "machine_id", "alias": "ID Mesin", "include": true, "order": 2},
    {"source_name": "temperature", "alias": "Suhu (°C)", "include": true, "order": 3},
    {"source_name": "pressure", "alias": "Tekanan (Bar)", "include": true, "order": 4}
  ],
  "datetime_config": {
    "date_column": "date",
    "time_column": "time",
    "output_format": "YYYY-MM-DD HH:MM:SS",
    "output_column_name": "DATETIME"
  },
  "export_config": {
    "format": "xlsx",
    "include_totals": true,
    "total_columns": ["temperature", "pressure"],
    "total_aggregations": ["SUM", "AVERAGE"]
  }
}
```

---

*Dokumen ini merupakan Product Requirements Document versi 1.0. Semua spesifikasi dapat berubah berdasarkan feedback pengguna dan prioritas bisnis.*

*Dibuat oleh: Tim Produk DataForge*  
*Terakhir diperbarui: April 2026*
