"""Second pass: for slugs without an image, do a Commons search,
then resolve the first promising filename to a direct URL and HEAD-check.
"""
import json
import time
import urllib.parse
import urllib.request

UA = "tg-shop-portfolio-seed/1.0 (educational; contact: alexxxmaxxx2323@gmail.com)"

# slug -> search query for Commons (we filter results client-side).
# good_keywords: ALL must appear (case-insensitive) in the file title
# bad_keywords: NONE may appear
QUERIES = {
    "nike-pegasus-40": (
        "Nike Pegasus 40 sneaker",
        ["pegasus"],
        ["store", "logo", "shoebox"],
    ),
    "adidas-ultraboost": (
        "Adidas Ultraboost",
        ["ultraboost"],
        ["box", "logo", "store"],
    ),
    "adidas-samba-og": (
        "Adidas Samba shoe",
        ["samba"],
        ["dance", "music", "festival", "logo", "carnival"],
    ),
    "nb-574": (
        "New Balance 574 shoe",
        ["574"],
        ["store", "logo"],
    ),
    "nb-990v6": (
        "New Balance 990",
        ["990"],
        ["store", "logo"],
    ),
    "puma-rs-x": (
        "Puma RS-X sneaker",
        ["rs-x"],
        ["logo", "store"],
    ),
    "asics-gel-lyte-iii": (
        "Asics Gel-Lyte III",
        ["gel"],
        ["logo", "store"],
    ),
    "reebok-classic-leather": (
        "Reebok Classic Leather shoe",
        ["reebok", "classic"],
        ["logo", "store", "stadium"],
    ),
    "reebok-club-c-85": (
        "Reebok Club C 85",
        ["club"],
        ["logo", "store", "stadium"],
    ),
    "vans-sk8-hi": (
        "Vans Sk8 Hi shoe",
        ["sk8"],
        ["logo", "store"],
    ),
    "converse-chuck-taylor": (
        "Converse Chuck Taylor All Stars shoe",
        ["chuck", "taylor"],
        ["logo", "store", "bridge"],
    ),
    "converse-chuck-70": (
        "Converse Chuck 70 shoe",
        ["chuck", "70"],
        ["logo", "store"],
    ),
    "puma-suede-classic": (
        "Puma Suede Classic shoe",
        ["suede"],
        ["logo", "store"],
    ),
    "timberland-6-inch": (
        "Timberland 6-inch yellow boot",
        ["timberland"],
        ["logo", "store", "tree", "forest"],
    ),
    "timberland-earthkeepers": (
        "Timberland Earthkeepers boot",
        ["earthkeepers"],
        ["logo", "store"],
    ),
    "dr-martens-1460": (
        "Dr Martens 1460 boot",
        ["1460"],
        ["logo", "store", "sole"],
    ),
    "dr-martens-jadon": (
        "Dr Martens Jadon platform boot",
        ["jadon"],
        ["logo", "store"],
    ),
    "dr-martens-1461": (
        "Dr Martens 1461 shoe",
        ["1461"],
        ["logo", "store"],
    ),
    "palladium-pampa-hi": (
        "Palladium Pampa Hi boot",
        ["palladium", "pampa"],
        ["logo", "metal", "element", "chemistry"],
    ),
}


def http_get(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"   HTTP error: {e}")
        return None


def search_commons(query: str, limit: int = 20) -> list[str]:
    """Return list of File: titles matching the query."""
    api = (
        "https://commons.wikimedia.org/w/api.php"
        "?action=query&list=search&srnamespace=6&format=json"
        f"&srlimit={limit}&srsearch=" + urllib.parse.quote(query)
    )
    body = http_get(api)
    if not body:
        return []
    try:
        data = json.loads(body)
        return [
            hit["title"].replace("File:", "", 1)
            for hit in data.get("query", {}).get("search", [])
        ]
    except Exception:
        return []


def commons_url(filename: str) -> str | None:
    api = (
        "https://commons.wikimedia.org/w/api.php"
        "?action=query&prop=imageinfo&iiprop=url&format=json&titles="
        + urllib.parse.quote("File:" + filename)
    )
    body = http_get(api)
    if not body:
        return None
    try:
        data = json.loads(body)
        for _, page in data.get("query", {}).get("pages", {}).items():
            if "imageinfo" in page:
                return page["imageinfo"][0]["url"]
    except Exception:
        return None
    return None


def head_ok(url: str) -> tuple[bool, str]:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
            ctype = r.headers.get("content-type", "")
            return (code == 200 and ctype.startswith("image/")), f"{code} {ctype}"
    except Exception as e:
        return False, str(e)


def filter_titles(titles: list[str], good: list[str], bad: list[str]) -> list[str]:
    out = []
    for t in titles:
        tl = t.lower()
        # Drop non-image extensions
        ext_ok = any(tl.endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp"))
        if not ext_ok:
            continue
        if not all(g in tl for g in good):
            continue
        if any(b in tl for b in bad):
            continue
        out.append(t)
    return out


def main() -> None:
    results: dict[str, str | None] = {}
    notes: dict[str, str] = {}

    for slug, (query, good, bad) in QUERIES.items():
        print(f"\n[{slug}] search: {query}")
        titles = search_commons(query, limit=25)
        time.sleep(1.5)
        candidates = filter_titles(titles, good, bad)
        if not candidates:
            print(f"   no matching titles among {len(titles)} hits")
            results[slug] = None
            notes[slug] = "no matching Commons file"
            continue
        print(f"   matching: {candidates[:5]}")
        found = None
        for fname in candidates[:5]:
            url = commons_url(fname)
            time.sleep(1.5)
            if not url:
                print(f"   - {fname}: resolve failed")
                continue
            ok, info = head_ok(url)
            time.sleep(0.5)
            if ok:
                print(f"   + {fname} -> {url}  [{info}]")
                found = url
                break
            else:
                print(f"   - {fname}: HEAD {info}")
        results[slug] = found
        if not found:
            notes[slug] = "no working candidate"

    print("\n\n========= RESULTS =========")
    for slug, url in results.items():
        print(f'    "{slug}": {url!r},  # {notes.get(slug, "ok")}')


if __name__ == "__main__":
    main()
