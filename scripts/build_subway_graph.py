#!/usr/bin/env python3
"""Build subway-graph.json from MTA static GTFS for client-side routing.

Output: stations (parent stops), directed ride edges with median scheduled
run times, per-route median weekday headways (07:00-20:00), transfer walk
times, and official route colors.

Usage: python3 scripts/build_subway_graph.py [--fresh]
"""
import argparse
import csv
import io
import json
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from itertools import pairwise
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".cache" / "rentmap"
OUT = REPO / "subway-graph.json"
GTFS_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
WINDOW = (7 * 3600, 20 * 3600)  # weekday 07:00-20:00 for headways


def hhmmss(s: str) -> int:
    h, m, sec = s.split(":")
    return int(h) * 3600 + int(m) * 60 + int(sec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    z = CACHE / "gtfs_subway.zip"
    if args.fresh or not z.exists():
        z.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {GTFS_URL}")
        with urllib.request.urlopen(GTFS_URL) as r:
            z.write_bytes(r.read())

    zf = zipfile.ZipFile(z)
    read = lambda name: csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))

    # parent stations + child->parent mapping
    parent_of, stations = {}, {}
    for s in read("stops.txt"):
        if s.get("location_type") == "1":
            stations[s["stop_id"]] = {
                "id": s["stop_id"], "name": s["stop_name"],
                "lat": round(float(s["stop_lat"]), 6), "lng": round(float(s["stop_lon"]), 6),
                "routes": set(),
            }
    for s in read("stops.txt"):
        if s.get("location_type") != "1":
            parent_of[s["stop_id"]] = s.get("parent_station") or s["stop_id"]

    # weekday service ids
    weekday_sids = {c["service_id"] for c in read("calendar.txt")
                    if all(c[d] == "1" for d in ("monday", "tuesday", "wednesday", "thursday", "friday"))}

    routes = {r["route_id"]: {
        "id": r["route_id"],
        "name": r.get("route_short_name") or r.get("route_long_name"),
        "color": "#" + (r.get("route_color") or "6D6E71"),
        "textColor": "#" + (r.get("route_text_color") or "FFFFFF"),
    } for r in read("routes.txt")}

    trip_route = {t["trip_id"]: t["route_id"] for t in read("trips.txt")
                  if t["service_id"] in weekday_sids}
    print(f"{len(stations)} stations, {len(trip_route)} weekday trips")

    # stream stop_times grouped by trip (file is trip-ordered)
    run_samples = defaultdict(list)          # (route, a, b) -> [seconds]
    departures = defaultdict(list)           # (route, station, direction-ish first stop) -> [dep seconds]
    cur_trip, cur_seq = None, []

    def flush():
        if not cur_trip or cur_trip not in trip_route:
            return
        rid = trip_route[cur_trip]
        seq = sorted(cur_seq, key=lambda x: x[0])
        for i in range(len(seq) - 1):
            _, dep_a, sta_a = seq[i]
            _, dep_b, sta_b = seq[i + 1]
            if sta_a == sta_b:
                continue
            dt = dep_b - dep_a
            if 30 <= dt <= 1800:
                run_samples[(rid, sta_a, sta_b)].append(dt)
        if seq:
            first_dep = seq[0][1]
            if WINDOW[0] <= first_dep <= WINDOW[1]:
                for _, dep, sta in seq:
                    departures[(rid, sta)].append(dep)

    for st in read("stop_times.txt"):
        tid = st["trip_id"]
        if tid != cur_trip:
            flush()
            cur_trip, cur_seq = tid, []
        if tid not in trip_route:
            continue
        p = parent_of.get(st["stop_id"], st["stop_id"])
        if p not in stations:
            continue
        try:
            cur_seq.append((int(st["stop_sequence"]), hhmmss(st["departure_time"]), p))
        except (ValueError, KeyError):
            continue
    flush()

    # edges: median scheduled run time per (route, a, b)
    edges = []
    used_routes = set()
    for (rid, a, b), samples in run_samples.items():
        if len(samples) < 5:
            continue
        edges.append({"r": rid, "a": a, "b": b, "m": round(statistics.median(samples) / 60, 2)})
        stations[a]["routes"].add(rid)
        stations[b]["routes"].add(rid)
        used_routes.add(rid)

    # headway: per route, median gap between consecutive departures per station,
    # then median across that route's stations
    headway = {}
    for rid in used_routes:
        gaps = []
        for (r2, sta), deps in departures.items():
            if r2 != rid or len(deps) < 8:
                continue
            deps = sorted(deps)
            g = [b - a for a, b in pairwise(deps) if 60 <= b - a <= 3600]
            if g:
                gaps.append(statistics.median(g))
        headway[rid] = round((statistics.median(gaps) if gaps else 600) / 60, 1)

    transfers = []
    seen = set()
    for t in read("transfers.txt"):
        a = parent_of.get(t["from_stop_id"], t["from_stop_id"])
        b = parent_of.get(t["to_stop_id"], t["to_stop_id"])
        if a == b or a not in stations or b not in stations or (a, b) in seen:
            continue
        seen.add((a, b))
        transfers.append({"a": a, "b": b, "m": round(int(t.get("min_transfer_time") or 180) / 60, 1)})

    out = {
        "generated_from": "MTA static GTFS (weekday schedules)",
        "stations": [{**s, "routes": sorted(s["routes"])} for s in stations.values() if s["routes"]],
        "edges": edges,
        "headwayMin": headway,
        "transfers": transfers,
        "routes": {rid: routes[rid] for rid in used_routes if rid in routes},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT} — {len(out['stations'])} stations, {len(edges)} edges, "
          f"{len(transfers)} transfers, {len(used_routes)} routes, {kb} KB")


if __name__ == "__main__":
    main()
