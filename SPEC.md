# rent map — spec

An interactive NYC "where should I live" optimizer at `/rentmap` on jean.land
(static site, Vercel, `pages/` is the output dir; standalone HTML pages pass through build.js).

## Problem statement

Given: a user-entered list of destinations (journeys) with weights (trips/week),
apartment-size filter, and rent data — find the cheapest places to live from which
those journeys are fastest, or vice versa. Objective, evaluated by exact enumeration
(no descent — the space is a few hundred candidate locations):

    cost(n) = rent(n) + λ · avgMinutes(n)       λ in $/mo per minute
    avgMinutes(n) = Σᵢ wᵢ·minutes(n, Dᵢ) / Σᵢ wᵢ   (trip-weighted one-way)

Plus the Pareto frontier over (rent, avgMinutes) — the full solution set for all λ.

## v1 (shipped, commit 031fbd5)

- 176 StreetEasy neighborhoods, trailing-12mo median asking rent × 5 bedroom sizes
  (`scripts/build_rentmap_data.py` → `pages/rentmap-data.json`).
- Single pin, straight-line km, λ slider, linked Leaflet map + SVG scatter,
  Pareto frontier, argmin tile, table view, light/dark.

## v2 (shipped in this repo)

Decision (per Andrew Kaplan's advice): build around **Google Maps Platform** instead
of a GTFS pipeline — transit scheduling, route polylines, geocoding and autocomplete
come from the API; the free tier is protected by caching. GTFS precompute remains the
documented key-free alternative (see Research).

- **Minutes, not km.** Distance Matrix API per (candidate, destination, mode);
  modes transit + walking both fetched, **fastest wins automatically** (no mode
  picker). Scheduled departure: next Monday 9:00am. 30-day localStorage cache —
  API is touched only when a pin moves (Andrew: "cache the distances").
- **No λ slider.** ε-constraint formulation instead: rent cap + commute cap sliders,
  objective toggle (cheapest rent | shortest commute), exact argmin over the feasible
  set by enumeration. Pareto frontier always shown; caps drawn as guide lines,
  infeasible candidates faded.
- **Multiple destinations**: address dropdown (Places autocomplete with key,
  OSM Photon without), click-to-add, per-journey trips/week weight, drag pins.
- **Pasted listings**: address + rent → geocoded, becomes a first-class candidate
  (diamond mark), auto-selected with routes drawn on add.
- **Precise routes**: click a candidate → Directions API per destination in the
  winning mode; transit steps drawn in the line's official color with line pills +
  per-leg minutes; walking legs dashed.
- **Live listings**: NO scraping — StreetEasy has no public listings API and its
  ToS forbids scraping (decision: hold this line). Every neighborhood deep-links to
  the live StreetEasy search for its area (+ beds filter).
- **No key → fallback**: Leaflet + CARTO tiles, straight-line km, Photon address
  search; banner explains how to add a key. `GMAPS_KEY_DEFAULT` in index.html or
  localStorage.

## Data sources (verified 2026-08-07)

- StreetEasy: https://cdn-charts.streeteasy.com/rentals/{All,Studio,OneBd,TwoBd,ThreePlusBd}/medianAskingRent_*.zip
  (no CORS — must be build-time; attribute "StreetEasy"; no formal license published)
- MTA subway GTFS static (shelved alternative): https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip
- Google Maps Platform: Maps JS, Distance Matrix, Directions, Places, Geocoding (referrer-restricted key)
- NYC NTA 2020 boundaries (centroids): data.cityofnewyork.us 9nt8-h7nd
- Better polygon source if needed later: HodgesWardElliott/custom-nyc-neighborhoods (139/176 exact)

## Research findings (agent-verified)

No existing tool combines neighborhood median rent + arbitrary destination +
bedroom toggle. Nearest: RentHop subway-station rent map, Trulia rent-near-transit,
Mapnificent (isochrones, no rent), StreetEasy's own commute filter (listings-side).
Free isochrone APIs (ORS, Mapbox) have NO transit profile; TravelTime does but is
trial-limited → GTFS precompute is the right architecture.

## Constraints / decisions log

- Never invent numeric constants: walk 1.4 m/s and bike 15 km/h are cited planning
  standards, labeled in the UI; waits/rides are computed from GTFS schedules.
- All commute figures in minutes.
- Dataviz per bundled skill: validated palette (blue series #2a78d6/#3987e5,
  winner orange #eb6834/#d95926, sequential blue ramp), table-view twin, tooltips,
  light+dark.
