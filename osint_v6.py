#!/usr/bin/env python3
"""OSINT Indonesia v6 - Exposure Checker (No HP & NIK)
Fokus: cek jejak digital NOMOR MILIK SENDIRI / yang ada izinnya.
Install: pip install requests beautifulsoup4 phonenumbers
"""
import argparse, base64, html as H, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
try:
    import phonenumbers
    from phonenumbers import PhoneNumberType as PT
except ImportError:
    phonenumbers = None

TIMEOUT = 12
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
}
S = requests.Session()
S.headers.update(HEADERS)

# ---------------------------------------------------------------- DATA
PROVIDER = {}
for _prov, _pre in {
    "Telkomsel (simPATI/Kartu As/Loop/by.U)": "0811 0812 0813 0821 0822 0823 0851 0852 0853",
    "Indosat (IM3/Mentari)": "0814 0815 0816 0855 0856 0857 0858",
    "XL": "0817 0818 0819 0859 0877 0878 0879",
    "Axis (grup XL)": "0831 0832 0833 0838",
    "Tri (3)": "0895 0896 0897 0898 0899",
    "Smartfren": "0881 0882 0883 0884 0885 0886 0887 0888 0889",
}.items():
    for _p in _pre.split():
        PROVIDER[_p] = _prov

PROVINSI = {
    "11": "Aceh", "12": "Sumatera Utara", "13": "Sumatera Barat", "14": "Riau",
    "15": "Jambi", "16": "Sumatera Selatan", "17": "Bengkulu", "18": "Lampung",
    "19": "Kep. Bangka Belitung", "21": "Kepulauan Riau", "31": "DKI Jakarta",
    "32": "Jawa Barat", "33": "Jawa Tengah", "34": "DI Yogyakarta", "35": "Jawa Timur",
    "36": "Banten", "51": "Bali", "52": "Nusa Tenggara Barat", "53": "Nusa Tenggara Timur",
    "61": "Kalimantan Barat", "62": "Kalimantan Tengah", "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur", "65": "Kalimantan Utara", "71": "Sulawesi Utara",
    "72": "Sulawesi Tengah", "73": "Sulawesi Selatan", "74": "Sulawesi Tenggara",
    "75": "Gorontalo", "76": "Sulawesi Barat", "81": "Maluku", "82": "Maluku Utara",
    "91": "Papua", "92": "Papua Barat", "93": "Papua Selatan", "94": "Papua Tengah",
    "95": "Papua Pegunungan", "96": "Papua Barat Daya",
}

def load_wilayah(path="kode_wilayah.json"):
    """Return {kode_tanpa_titik: nama} dari kode_wilayah.json (opsional)."""
    flat = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for pk, pv in data.items():
            flat[pk.replace(".", "")] = pv.get("nama", "")
            for kk, kv in pv.get("kabupaten", {}).items():
                flat[kk.replace(".", "")] = kv.get("nama", "")
                for ck, cv in kv.get("kecamatan", {}).items():
                    flat[ck.replace(".", "")] = cv
    except Exception:
        pass
    return flat
WILAYAH = load_wilayah()

# ---------------------------------------------------------------- DECODER (offline)
def decode_nik(n):
    if not (n.isdigit() and len(n) == 16):
        return None
    dd, mm, yy = int(n[6:8]), int(n[8:10]), int(n[10:12])
    gender = "Laki-laki"
    if dd > 40:
        dd, gender = dd - 40, "Perempuan"
    year = 2000 + yy if yy <= date.today().year % 100 else 1900 + yy
    try:
        dob = date(year, mm, dd)
    except ValueError:
        dob = None
    age = None
    if dob:
        t = date.today()
        age = t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))
    info = {
        "nik_masked": n[:6] + "******" + n[-4:],
        "provinsi": PROVINSI.get(n[:2], "Kode tidak dikenal"),
        "kab_kota": WILAYAH.get(n[:4], "(jalankan osint_builder.py untuk nama)"),
        "kecamatan": WILAYAH.get(n[:6], "(jalankan osint_builder.py untuk nama)"),
        "tgl_lahir": dob.isoformat() if dob else "Tidak valid",
        "umur": age, "gender": gender, "no_urut": n[12:],
    }
    info["struktur_valid"] = n[:2] in PROVINSI and dob is not None and dob <= date.today()
    return info

def phone_info(raw):
    d = re.sub(r"[^\d+]", "", raw)
    if d.startswith("+62"): d = d[3:]
    elif d.startswith("62"): d = d[2:]
    elif d.startswith("0"): d = d[1:]
    local, core = "0" + d, d
    info = {"lokal": local, "e164": "+62" + core,
            "provider": PROVIDER.get(local[:4], "Tidak diketahui"),
            "valid": bool(re.fullmatch(r"8\d{8,11}", core))}
    if phonenumbers:
        try:
            p = phonenumbers.parse("+62" + core)
            info["valid"] = phonenumbers.is_valid_number(p)
            info["tipe"] = {PT.MOBILE: "Seluler", PT.FIXED_LINE: "Telepon rumah"}.get(
                phonenumbers.number_type(p), "Lainnya")
            info["internasional"] = phonenumbers.format_number(
                p, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except Exception:
            pass
    info["_core"] = core
    return info

# ---------------------------------------------------------------- SEARCH
def unwrap(url):
    """Bongkar redirect Bing (bing.com/ck/a?u=a1...) & DuckDuckGo (/l/?uddg=...)."""
    p = urlparse(url)
    if p.netloc.endswith("bing.com") and p.path.startswith("/ck/"):
        u = parse_qs(p.query).get("u", [""])[0]
        if u.startswith("a1"):
            b = u[2:]
            try:
                return base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
            except Exception:
                return url
    if p.netloc.endswith("duckduckgo.com") and p.path.startswith("/l/"):
        return parse_qs(p.query).get("uddg", [url])[0]
    return url

def parse_bing(t):
    out = []
    for li in BeautifulSoup(t, "html.parser").select("li.b_algo"):
        a = li.select_one("h2 a")
        if a and a.get("href"):
            sn = li.select_one(".b_caption p") or li.select_one("p")
            out.append((a.get_text(" ", strip=True), unwrap(a["href"]),
                        sn.get_text(" ", strip=True) if sn else ""))
    return out

def parse_ddg(t):
    out = []
    for d in BeautifulSoup(t, "html.parser").select("div.result"):
        a = d.select_one("a.result__a")
        if a and a.get("href"):
            sn = d.select_one(".result__snippet")
            href = a["href"]
            if href.startswith("//"): href = "https:" + href
            out.append((a.get_text(" ", strip=True), unwrap(href),
                        sn.get_text(" ", strip=True) if sn else ""))
    return out

def run_search(engine, q):
    try:
        if engine == "Bing":
            r = S.get("https://www.bing.com/search", timeout=TIMEOUT,
                      params={"q": q, "setlang": "id", "cc": "ID", "count": 20})
            parser = parse_bing
        else:
            r = S.post("https://html.duckduckgo.com/html/", timeout=TIMEOUT,
                       data={"q": q, "kl": "id-id"})
            parser = parse_ddg
        if r.status_code != 200:
            return [], f"{engine}: HTTP {r.status_code} (kemungkinan rate-limit/captcha)"
        res = parser(r.text)
        return res, (None if res else f"{engine}: 0 hasil (diblokir/captcha atau memang kosong)")
    except requests.exceptions.SSLError:
        return [], f"{engine}: gangguan SSL/DNS dari jaringanmu (bukan bug tool), coba ganti DNS/VPN"
    except Exception as e:
        return [], f"{engine}: {e}"

def contains_number(text, core):
    return core in re.sub(r"\D", "", text or "")

def page_has(url, core):
    try:
        r = S.get(url, timeout=8, stream=True)
        if "text/html" not in r.headers.get("content-type", ""):
            return False
        raw = r.raw.read(400_000, decode_content=True).decode("utf-8", "ignore")
        return contains_number(BeautifulSoup(raw, "html.parser").get_text(" "), core)
    except Exception:
        return False

def phone_queries(i):
    c, l = i["_core"], i["lokal"]
    f = [l, f"+62{c}", f"62{c}", f"{l[:4]}-{l[4:8]}-{l[8:]}", f"{l[:4]} {l[4:8]} {l[8:]}"]
    qs = [f'"{x}"' for x in f]
    qs += [f'"{l}" (jual OR beli OR olshop OR cod OR wa OR whatsapp)',
           f'"{l}" (penipu OR scam OR rekber OR "laporan penipuan")',
           f'"{l}" (cv OR resume OR lowongan OR kontak OR alamat)',
           f'"{l}" (instagram OR facebook OR tiktok OR linkedin)']
    return qs

def nik_queries(n):
    return [f'"{n}"']

def search_all(queries, core, verify, engines=("Bing", "DuckDuckGo")):
    seen, hits, errors = {}, [], []
    for q in queries:
        for e in engines:
            res, err = run_search(e, q)
            if err: errors.append(err)
            for title, url, sn in res:
                key = urlparse(url)._replace(fragment="").geturl()
                if key in seen: continue
                seen[key] = 1
                hits.append({"title": title, "url": url, "snippet": sn, "query": q,
                             "domain": urlparse(url).netloc.removeprefix("www."),
                             "match": contains_number(title + " " + sn, core)})
            time.sleep(1.5)  # jangan agresif
    if verify:
        todo = [h for h in hits if not h["match"]]
        with ThreadPoolExecutor(8) as ex:
            for h, ok in zip(todo, ex.map(lambda h: page_has(h["url"], core), todo)):
                h["match"] = ok
                h["verified_by"] = "isi halaman" if ok else ""
    hits.sort(key=lambda h: not h["match"])
    return hits, sorted(set(errors))

# ---------------------------------------------------------------- PROSES
def consent(yes):
    if yes: return True
    a = input("Nomor/NIK ini milik Anda sendiri atau Anda punya izin tertulis pemiliknya? (y/n): ")
    return a.strip().lower() in ("y", "ya")

def process(t, args):
    t = t.strip()
    out = {"target": t}
    if t.isdigit() and len(t) == 16:
        out["jenis"] = "NIK"; out["info"] = decode_nik(t)
        core, queries, shown = t, nik_queries(t), t[:6] + "******" + t[-4:]
    elif re.fullmatch(r"(\+62|62|0)8[\d\s\-]{8,14}", t):
        out["jenis"] = "HP"; out["info"] = phone_info(t)
        core, queries, shown = out["info"]["_core"], phone_queries(out["info"]), t
    else:
        print(f"[!] Format tidak dikenal: {t}"); return None
    out["shown"] = shown
    out["info"] = {k: v for k, v in out["info"].items() if not k.startswith("_")}
    print(f"\n=== {out['jenis']}: {shown}")
    for k, v in out["info"].items(): print(f"  {k:15}: {v}")
    if args.no_search:
        return out
    if not consent(args.yes):
        print("  (pencarian online dilewati)"); return out
    hits, errs = search_all(queries, core, args.verify)
    out["hits"], out["errors"] = hits, errs
    m = [h for h in hits if h["match"]]
    print(f"  Ditemukan {len(hits)} link, {len(m)} memuat nomor/NIK tersebut")
    for h in m[:10]: print(f"   * {h['domain']} | {h['title'][:70]}\n     {h['url']}")
    for e in errs: print("  [!]", e)
    return out

def export_html(results, path):
    css = ("body{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;background:#f6f7f9}"
           ".c{background:#fff;border-radius:10px;padding:1rem 1.2rem;margin:1rem 0;box-shadow:0 1px 3px #0002}"
           "table{border-collapse:collapse}td{padding:2px 14px 2px 0;vertical-align:top}"
           ".b{background:#16a34a;color:#fff;border-radius:6px;padding:1px 7px;font-size:.75rem}"
           ".h{border-top:1px solid #eee;padding:.6rem 0}.h a{font-weight:600;text-decoration:none}"
           ".d{color:#666;font-size:.8rem}.w{color:#b45309}")
    o = [f"<!doctype html><meta charset=utf-8><title>OSINT Report</title><style>{css}</style>",
         f"<h1>OSINT Report</h1><p class=d>{datetime.now():%d %b %Y %H:%M}</p>"]
    for r in results:
        o.append(f"<div class=c><h2>{r['jenis']}: {H.escape(r['shown'])}</h2><table>")
        for k, v in r["info"].items():
            o.append(f"<tr><td><b>{H.escape(k)}</b></td><td>{H.escape(str(v))}</td></tr>")
        o.append("</table>")
        for e in r.get("errors", []): o.append(f"<p class=w>⚠ {H.escape(e)}</p>")
        hits = r.get("hits", [])
        if "hits" in r:
            o.append(f"<h3>Jejak online ({sum(h['match'] for h in hits)} cocok / {len(hits)} link)</h3>")
        for h in hits:
            badge = "<span class=b>memuat nomor</span> " if h["match"] else ""
            o.append(f"<div class=h>{badge}<a href='{H.escape(h['url'])}' target=_blank rel=noopener>"
                     f"{H.escape(h['title'] or h['url'])}</a><div class=d>{H.escape(h['domain'])}</div>"
                     f"<div>{H.escape(h['snippet'])}</div></div>")
        o.append("</div>")
    with open(path, "w", encoding="utf-8") as f: f.write("\n".join(o))
    print(f"\n[✓] Report: {path}")

def main():
    ap = argparse.ArgumentParser(description="OSINT Indonesia v6 - exposure checker")
    ap.add_argument("targets", nargs="*", help="No HP / NIK")
    ap.add_argument("-f", "--file", help="file .txt berisi target (1 per baris)")
    ap.add_argument("--verify", action="store_true", help="buka tiap halaman & cek apakah benar memuat nomor")
    ap.add_argument("--no-search", action="store_true", help="hanya decode offline")
    ap.add_argument("--yes", action="store_true", help="lewati prompt izin (saya pemilik/berwenang)")
    ap.add_argument("-o", "--out", default=f"output/report_{datetime.now():%Y%m%d_%H%M%S}.html")
    a = ap.parse_args()
    targets = list(a.targets)
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            targets += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not targets:
        targets = [input("Masukkan No HP / NIK: ")]
    targets = list(dict.fromkeys(targets))
    results = [r for r in (process(t, a) for t in targets) if r]
    if results:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        export_html(results, a.out)

if __name__ == "__main__":
    main()