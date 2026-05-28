"""Resolve Wikimedia Commons filenames to direct upload.wikimedia.org URLs
and verify each URL via HEAD request.

Usage: python _resolve_images.py
"""
import json
import time
import urllib.parse
import urllib.request

# slug -> candidate Commons filenames (without "File:" prefix).
# Order matters: first that works wins.
CANDIDATES = {
    "nike-air-force-1": [
        "Nike air Force 1 white on white.jpg",
        "Nike AF1.JPG",
        "Air Force 1.JPG",
        "Nike Air Force 1.jpg",
    ],
    "nike-air-max-90": [
        "Nike Air Max 90.jpg",
        "Air Max 90.png",
        "Air max 90.JPG",
    ],
    "nike-pegasus-40": [
        "Nike Air Zoom Pegasus 40.jpg",
        "Nike Pegasus 40.jpg",
    ],
    "adidas-stan-smith": [
        "Adidas Stan Smiths sneaker.jpg",
        "Stan Smith white and green.png",
        "Adidas Stan Smith wht-blk.jpg",
    ],
    "adidas-ultraboost": [
        "Adidas Ultra Boost.jpg",
        "Adidas Ultraboost.jpg",
        "Ultraboost.jpg",
    ],
    "adidas-samba-og": [
        "Adidas Samba OG.jpg",
        "Adidas Samba.jpg",
    ],
    "nb-574": [
        "New Balance 574.jpg",
        "New Balance 574 shoe.gif",
    ],
    "nb-990v6": [
        "New Balance 990v6.jpg",
        "New Balance 990.jpg",
    ],
    "puma-rs-x": [
        "Puma RS-X.jpg",
        "PUMA RS-X.jpg",
    ],
    "asics-gel-lyte-iii": [
        "Asics Gel Lyte III.jpg",
        "ASICS Gel-Lyte III.jpg",
    ],
    "reebok-classic-leather": [
        "Reebok Classic Leather.jpg",
        "Reebok Classics.jpg",
    ],
    "reebok-club-c-85": [
        "Reebok Club C 85.jpg",
        "Reebok Club C.jpg",
    ],
    "vans-old-skool": [
        "Vans Old Skool Nautical Blue.gif",
        "Vans Old Skool.jpg",
    ],
    "vans-authentic": [
        "Vans Authentic.jpg",
        "Vans Authentic schwarz.jpg",
    ],
    "vans-sk8-hi": [
        "Vans sk8-hi.jpg",
    ],
    "converse-chuck-taylor": [
        "Converse Chuck Taylor All-Stars (51091002425).jpg",
        "Red and blue Chuck Taylor All-Stars sneakers, 2010.jpg",
    ],
    "converse-chuck-70": [
        "Converse-Chuck 70.jpg",
        "Converse Chuck 70.jpg",
    ],
    "puma-suede-classic": [
        "Puma Suede Classic.jpg",
        "Puma Suede.jpg",
    ],
    "timberland-6-inch": [
        "Timberland 6-inch boots.jpg",
        "Timberland boots.jpg",
        "Timberland Boot Company Premium 6-inch.jpg",
    ],
    "timberland-earthkeepers": [
        "Timberland Earthkeepers.jpg",
    ],
    "dr-martens-1460": [
        "Doctors 1460 Black Worn.jpg",
        "Dr martens boots.jpg",
        "DocMartens.jpg",
    ],
    "dr-martens-jadon": [
        "Dr Martens Jadon.jpg",
        "Dr. Martens Jadon.jpg",
    ],
    "dr-martens-1461": [
        "Dr Martens 1461.jpg",
        "Dr. Martens 1461.jpg",
        "Dr Martens Delray shoes.jpg",
    ],
    "palladium-pampa-hi": [
        "Palladium Pampa Hi.jpg",
        "Palladium boots.jpg",
    ],
}


def commons_url(filename: str) -> str | None:
    """Resolve a Commons filename to its direct upload.wikimedia.org URL."""
    api = (
        "https://commons.wikimedia.org/w/api.php"
        "?action=query&prop=imageinfo&iiprop=url&format=json&titles="
        + urllib.parse.quote("File:" + filename)
    )
    req = urllib.request.Request(api, headers={"User-Agent": "tg-shop-seed/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "imageinfo" in page:
                return page["imageinfo"][0]["url"]
            if "missing" in page:
                return None
    except Exception as e:
        print(f"  API error for {filename}: {e}")
    return None


def head_ok(url: str) -> tuple[bool, str]:
    """HEAD-check an image URL."""
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": "tg-shop-seed/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            ctype = r.headers.get("content-type", "")
            return (code == 200 and ctype.startswith("image/")), f"{code} {ctype}"
    except Exception as e:
        return False, str(e)


def main() -> None:
    results: dict[str, str | None] = {}
    notes: dict[str, str] = {}

    for slug, candidates in CANDIDATES.items():
        print(f"\n[{slug}]")
        found = None
        last_err = ""
        for fname in candidates:
            url = commons_url(fname)
            time.sleep(0.4)
            if not url:
                print(f"  - {fname}: not in Commons")
                last_err = f"missing in Commons: {fname}"
                continue
            ok, info = head_ok(url)
            if ok:
                print(f"  + {fname} -> {url}  [{info}]")
                found = url
                break
            else:
                print(f"  - {fname}: HEAD failed {info}")
                last_err = f"HEAD failed: {info}"
        results[slug] = found
        if not found:
            notes[slug] = last_err or "no working candidate"

    print("\n\n========= RESULTS =========")
    print("IMAGES = {")
    for slug, url in results.items():
        if url:
            print(f'    "{slug}": "{url}",')
        else:
            print(f'    "{slug}": None,  # {notes.get(slug, "?")}')
    print("}")
    ok = sum(1 for v in results.values() if v)
    print(f"\nFound: {ok}/{len(results)}; failed: {len(results) - ok}")


if __name__ == "__main__":
    main()
