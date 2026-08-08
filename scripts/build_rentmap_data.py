#!/usr/bin/env python3
"""Build pages/rentmap-data.json for the rent-vs-commute map.

Sources:
  - StreetEasy Data Dashboard median asking rent CSVs (public S3, monthly by
    neighborhood and bedroom count): https://streeteasy.com/blog/data-dashboard/
  - NYC NTA 2020 neighborhood boundaries (NYC Open Data) for centroids.

Usage:
  python3 scripts/build_rentmap_data.py            # uses/downloads cache in .cache/rentmap
  python3 scripts/build_rentmap_data.py --fresh    # force re-download
"""
import argparse
import csv
import io
import json
import re
import statistics
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".cache" / "rentmap"
OUT = REPO / "rentmap-data.json"

SE_BASE = "https://streeteasy-market-data-download.s3.amazonaws.com/rentals"
BEDROOMS = {
    "all": ("All", "medianAskingRent_All"),
    "studio": ("Studio", "medianAskingRent_Studio"),
    "1br": ("OneBd", "medianAskingRent_OneBd"),
    "2br": ("TwoBd", "medianAskingRent_TwoBd"),
    "3br": ("ThreePlusBd", "medianAskingRent_ThreePlusBd"),
}
NTA_URL = "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON"

# StreetEasy neighborhoods with no usable NTA2020 name match; centroids set by hand.
MANUAL_CENTROIDS = {
    "Bronxwood": (40.8746, -73.8625),
    "Central Harlem": (40.8116, -73.9465),
    "Central Park South": (40.7657, -73.9776),
    "Columbia St Waterfront District": (40.6875, -74.0022),
    "Greenwood": (40.6602, -73.9932),
    "Laconia": (40.8747, -73.8531),
    "Marble Hill": (40.8762, -73.9107),
    "Midtown East": (40.7549, -73.9722),
    "Midtown West": (40.7638, -73.9918),
    "Nolita": (40.7229, -73.9944),
    "Old Mill Basin": (40.6198, -73.9146),
    "Prospect Park South": (40.6479, -73.9683),
    "Rockaway All": (40.5860, -73.8150),
    "Seagate": (40.5762, -74.0083),
    "Stuyvesant Town/PCV": (40.7318, -73.9776),
    "Westchester Village": (40.8399, -73.8479),
    "Woodstock": (40.8156, -73.9019),
}


def fetch(url: str, dest: Path, fresh: bool) -> Path:
    if dest.exists() and not fresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as r:
        dest.write_bytes(r.read())
    return dest


def load_se_csv(path: Path) -> tuple[list[str], list[dict]]:
    """Return (month_columns, rows) from a StreetEasy zip."""
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        text = z.read(name).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    months = [c for c in rows[0] if re.fullmatch(r"\d{4}-\d{2}", c)]
    return months, rows


def trailing_median(row: dict, months: list[str], k: int = 12):
    """Median of the last k non-empty monthly values; None if fewer than 3."""
    vals = []
    for m in reversed(months):
        v = row.get(m, "")
        if v not in ("", None):
            vals.append(float(v))
        if len(vals) == k:
            break
    if len(vals) < 3:
        return None
    return round(statistics.median(vals))


def polygon_centroid(geom) -> tuple[float, float] | None:
    tot_a = cx = cy = 0.0
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        ring = poly[0]
        a = x = y = 0.0
        for i in range(len(ring) - 1):
            x0, y0 = ring[i]
            x1, y1 = ring[i + 1]
            cross = x0 * y1 - x1 * y0
            a += cross
            x += (x0 + x1) * cross
            y += (y0 + y1) * cross
        if a != 0:
            x /= 3 * a
            y /= 3 * a
            a = abs(a) / 2
            tot_a += a
            cx += x * a
            cy += y * a
    return (cy / tot_a, cx / tot_a) if tot_a else None


def norm(s: str) -> str:
    s = s.lower().replace("-", " ").replace(".", "").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def build_centroids(nta_path: Path, se_hoods: list[tuple[str, str]]) -> dict:
    d = json.loads(nta_path.read_text())
    ntas = []
    for f in d["features"]:
        p = f["properties"]
        if p["ntatype"] != "0":  # skip parks, cemeteries, airports
            continue
        c = polygon_centroid(f["geometry"])
        if c:
            ntas.append((p["ntaname"], p["boroname"], c))

    out = {}
    missing = []
    for name, boro in se_hoods:
        if name in MANUAL_CENTROIDS:
            out[name] = MANUAL_CENTROIDS[name]
            continue
        n = norm(name)
        hits = [t for t in ntas if norm(t[0]) == n and t[1] == boro]
        if not hits:
            hits = [t for t in ntas if t[1] == boro and (n in norm(t[0]) or norm(t[0]) in n)]
        if hits:
            lat = sum(h[2][0] for h in hits) / len(hits)
            lng = sum(h[2][1] for h in hits) / len(hits)
            out[name] = (round(lat, 5), round(lng, 5))
        else:
            missing.append((name, boro))
    if missing:
        raise SystemExit(f"no centroid for {missing}; add to MANUAL_CENTROIDS")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="force re-download of sources")
    args = ap.parse_args()

    rent_by_key = {}
    data_through = None
    for key, (s3dir, fname) in BEDROOMS.items():
        z = fetch(f"{SE_BASE}/{s3dir}/{fname}.zip", CACHE / f"{fname}.zip", args.fresh)
        months, rows = load_se_csv(z)
        data_through = max(data_through or "", months[-1])
        for row in rows:
            if row["areaType"] != "neighborhood":
                continue
            k = (row["areaName"], row["Borough"])
            rent_by_key.setdefault(k, {})[key] = trailing_median(row, months)

    # keep neighborhoods with at least an all-bedrooms figure
    hoods = [(k, v) for k, v in rent_by_key.items() if v.get("all")]
    centroids = build_centroids(
        fetch(NTA_URL, CACHE / "nta2020.geojson", args.fresh), [k for k, _ in hoods]
    )

    features = []
    for (name, boro), rents in sorted(hoods):
        lat, lng = centroids[name]
        features.append({"name": name, "boro": boro, "lat": lat, "lng": lng, "rent": rents})

    out = {
        "source": "StreetEasy Data Dashboard, median asking rent (trailing 12-month median per bedroom count)",
        "dataThrough": data_through,
        "neighborhoods": features,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"wrote {OUT} — {len(features)} neighborhoods, data through {data_through}")


if __name__ == "__main__":
    main()
