# 🇮🇩 OSINT Indonesia v6 — Exposure Checker

Tool untuk mengecek **jejak digital sebuah No HP atau NIK**: nomornya muncul di web mana saja, dan apa isi informasi dasar yang terkandung di nomor itu sendiri.

> ⚠️ **Gunakan hanya untuk nomor/NIK milik sendiri, atau dengan izin tertulis pemiliknya**
> (audit privasi pribadi, pengecekan nomor bisnis, pentest resmi). Mengumpulkan data pribadi orang lain tanpa izin
> dapat melanggar **UU PDP No. 27/2022** dan **UU ITE**. Tool akan menanyakan konfirmasi sebelum melakukan pencarian online.

## Yang berubah dari v5

| Masalah di v5 | Perbaikan di v6 |
|---|---|
| Hasil hanya "provider", link Bing tidak terbaca | Redirect `bing.com/ck/a?u=...` dan `duckduckgo.com/l/?uddg=...` dibongkar jadi URL asli |
| Hasil berupa JSON mentah | Report HTML rapi: judul, domain, snippet, link bisa diklik |
| Banyak hasil tidak relevan | Hanya ditandai **"memuat nomor"** jika nomor benar ada di judul/snippet; `--verify` membuka halaman untuk memastikan |
| Query cuma 1 format | Variasi format (`0812…`, `+62812…`, `0812-3456-…`) + query konteks (jual-beli, laporan penipuan, kontak, sosmed) |
| Google selalu diblokir | Dihapus; pakai Bing + DuckDuckGo, dengan jeda agar tidak kena rate-limit |
| Prefix provider usang | Prefix diperbarui (Telkomsel/by.U, Indosat, XL, Axis, Tri, Smartfren) + validasi `phonenumbers` |
| NIK hanya di-dork | **Decode offline**: provinsi, kab/kota, kecamatan, tanggal lahir, umur, gender, validasi struktur |
| NIK tampil penuh di report | NIK **dimasking** (`320807******0004`) |
| `kode_wilayah.json` kosong | Tetap dipakai kalau ada; nama provinsi sudah built-in (termasuk provinsi Papua baru) |

## Instalasi

```bash
pip install requests beautifulsoup4 phonenumbers
python3 osint_v6.py
```

(opsional) isi nama kab/kota & kecamatan untuk decode NIK:

```bash
python3 osint_builder.py
```

## Pemakaian

```bash
# satu target
python3 osint_v6.py 081234567890

# beberapa target, verifikasi isi halaman, lewati prompt (saya pemilik/berwenang)
python3 osint_v6.py 081234567890 3208074509870004 --verify --yes

# dari file (1 target per baris, baris # diabaikan)
python3 osint_v6.py -f targets.txt

# hanya decode offline, tanpa internet
python3 osint_v6.py 3208074509870004 --no-search

# tentukan lokasi report
python3 osint_v6.py 081234567890 -o hasil/cek.html
```

Report tersimpan di `output/report_<waktu>.html`.

## Catatan & batasan

* Bing/DuckDuckGo bisa menampilkan captcha atau membatasi request. Jika muncul `0 hasil`, tunggu beberapa menit atau ganti IP/jaringan.
* Prefix provider hanya menunjukkan operator **awal**; nomor bisa sudah pindah operator.
* Decode NIK hanya membaca struktur angka (bukan cek ke Dukcapil). Struktur valid ≠ NIK benar-benar terdaftar.
* Tool ini **tidak** mengakses data breach, database bocoran, atau layanan lookup identitas.

## Struktur

```
.
├── osint_v6.py        # tool utama
├── osint_builder.py   # opsional: download data wilayah
├── targets.txt
├── output/            # report HTML
└── README.md
```

## Note
```
silahkan kunjungi https://github.com/spyschools/osint-indonesia-v5 untuk mendapatkan versi sebelumnya
```
