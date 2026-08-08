# traphaus locator

Where should you live in NYC? Add the places you actually go (weighted by trips/week),
set a rent cap and a commute cap, and optimize for either cheapest rent or shortest
commute. Every neighborhood — plus any specific listing you paste in — is scored by
StreetEasy median asking rent against your trip-weighted door-to-door minutes.
Exact ε-constraint optimization by enumeration; Pareto frontier included. Click any
candidate to see its precise routes, train lines and all.

## Run

Static site — no build. Serve the repo root:

```sh
python3 -m http.server 8742
# open http://localhost:8742
```

## Google Maps key (for real minutes + routes)

Without a key the app runs in straight-line-distance fallback (still fully playable,
with an OSM/Photon address search). With a key you get real transit/walking minutes
(fastest mode auto-picked per trip, scheduled next-Monday-9am departure), exact route
polylines with train-line colors, Places autocomplete, and geocoding for pasted listings.

1. Create a key in Google Cloud console with: Maps JavaScript API, Distance Matrix API,
   Directions API, Places API, Geocoding API.
2. Restrict it by HTTP referrer to your domain.
3. Paste it into the banner on the page (stored in localStorage), or set
   `GMAPS_KEY_DEFAULT` in `index.html` for deploys.

All (origin, destination, mode) travel times are cached in localStorage for 30 days,
so the free tier is only touched when a pin actually moves.

## Data pipeline

```sh
python3 scripts/build_rentmap_data.py          # refresh rentmap-data.json
python3 scripts/build_rentmap_data.py --fresh  # force re-download of sources
```

Sources: StreetEasy Data Dashboard (median asking rent by neighborhood × bedroom count,
trailing-12-month median; attribute "StreetEasy") and NYC Open Data 2020 NTAs (centroids).
Listings are never scraped or stored — candidates deep-link to live StreetEasy searches.

See SPEC.md for the full design and decision log.
