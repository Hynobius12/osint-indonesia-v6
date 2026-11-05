#!/usr/bin/env python3
import json, requests
from concurrent.futures import ThreadPoolExecutor

BASE = "https://emsifa.github.io/api-wilayah-indonesia/api"

def get(path):
    for _ in range(3):
        try:
            r = requests.get(f"{BASE}/{path}.json", timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception:
            pass
    return []

provs = get("provinces")
if not provs:
    raise SystemExit("[!] Gagal ambil provinsi, cek koneksi/DNS")

wil, regs = {}, []
for p in provs:
    wil[p["id"]] = {"nama": p["name"].title(), "kabupaten": {}}
    for r in get(f"regencies/{p['id']}"):
        wil[p["id"]]["kabupaten"][r["id"]] = {"nama": r["name"].title(), "kecamatan": {}}
        regs.append((p["id"], r["id"]))
print(f"[*] {len(regs)} kab/kota, ambil kecamatan...")

with ThreadPoolExecutor(8) as ex:
    for (pid, rid), ds in zip(regs, ex.map(lambda x: get(f"districts/{x[1]}"), regs)):
        for d in ds:
            wil[pid]["kabupaten"][rid]["kecamatan"][d["id"]] = d["name"].title()

with open("kode_wilayah.json", "w", encoding="utf-8") as f:
    json.dump(wil, f, indent=2, ensure_ascii=False)
print("[✓] kode_wilayah.json tersimpan")