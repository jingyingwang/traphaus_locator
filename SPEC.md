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

## v2 (current work)

- **Minutes, not km.** Real subway commute times from MTA static GTFS
  (`scripts/build_subway_graph.py` → `pages/subway-graph.json`):
  stations, per-route median inter-station run times from weekday schedules,
  per-route median headways (wait = headway/2), transfer times from transfers.txt,
  MTA route colors. Client-side Dijkstra on (station × route) nodes.
- **Walk access/egress** at 1.4 m/s (standard planning value); pure-walk wins when
  faster. Optional bike mode (15 km/h, labeled estimate).
- **Multiple destinations**: click-to-add pins, each with name + trips/week weight.
- **Station layer** (toggle vs neighborhood layer): stations as organic cluster
  seeds; station rent = inverse-distance-weighted blend of StreetEasy neighborhood
  medians within the catchment, labeled as derived.
- **Precise routes**: clicking any candidate draws the actual station-by-station
  polyline per destination, colored by MTA line color, with a minutes breakdown
  (walk / wait / ride / transfer).
- **Live listings**: NO scraping — StreetEasy has no public listings API and its
  ToS forbids scraping (decision: hold this line). Instead every cluster/neighborhood
  deep-links to the live StreetEasy search for its area filtered by beds + max price
  (parameterized URL, slug from neighborhood name).

## Data sources (verified 2026-08-07)

- StreetEasy: https://cdn-charts.streeteasy.com/rentals/{All,Studio,OneBd,TwoBd,ThreePlusBd}/medianAskingRent_*.zip
  (no CORS — must be build-time; attribute "StreetEasy"; no formal license published)
- MTA subway GTFS static: https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip
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
