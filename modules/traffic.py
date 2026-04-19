"""
A Unique Route — Live Traffic Module

Fetches real-time traffic speed data from TomTom Traffic Flow API
and applies congestion factors to graph edges for accurate ETAs.

Strategy:
  1. Sample ~50 points in a grid along the origin-destination corridor
  2. Query TomTom Flow API for current vs free-flow speed at each point
  3. Build a KDTree over the sampled points
  4. For each graph edge, interpolate the nearest traffic sample → traffic_factor
  5. Cache results for 10 minutes to stay inside free-tier limits

Fallback:
  When the API is unavailable (no key, rate-limited, timeout), uses a
  time-of-day × road-class heuristic model.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import requests
import numpy as np
from scipy.spatial import cKDTree

log = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────
_traffic_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 600   # 10 minutes

# ── TomTom API ────────────────────────────────────────────────────────────────
TOMTOM_FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/"
    "flowSegmentData/absolute/21/json"
)

# ── Fallback: time-of-day × road-class speed ratios ──────────────────────────
# speed_ratio = current_speed / free_flow_speed  (0.0 = standstill, 1.0 = free flow)
#
# The base ratio represents the road's inherent capacity under non-peak
# conditions (i.e. how close to the speed limit traffic actually flows).
# Values near 1.0 = road typically allows free-flow speeds.

_BASE_RATIO = {
    "motorway":       0.95,
    "motorway_link":  0.90,
    "trunk":          0.92,
    "trunk_link":     0.88,
    "primary":        0.90,
    "primary_link":   0.85,
    "secondary":      0.92,
    "secondary_link": 0.88,
    "tertiary":       0.94,
    "tertiary_link":  0.92,
    "residential":    0.97,
    "living_street":  0.99,
    "unclassified":   0.95,
    "service":        0.97,
}

# Peak-hour multiplier — covers ALL 24 hours for Chennai traffic patterns.
# Applied on top of base ratio:  speed_ratio = base × multiplier
#
# Chennai traffic profile:
#   0–5 AM  : Near empty roads, free flow
#   6–7 AM  : Early commuters, light traffic
#   8–10 AM : Morning rush (Anna Salai, OMR, GST Road jammed)
#   11–16   : Midday, moderate flow
#   17–20   : Evening rush (peak congestion, especially 18:00)
#   21–23   : Traffic easing, approaching free flow
_PEAK_MULTIPLIER = {
    0:  1.00,   1: 1.00,   2: 1.00,   3: 1.00,
    4:  1.00,   5: 0.98,   6: 0.92,   7: 0.80,
    8:  0.60,   9: 0.55,  10: 0.70,  11: 0.82,
    12: 0.83,  13: 0.84,  14: 0.83,  15: 0.80,
    16: 0.75,  17: 0.55,  18: 0.45,  19: 0.50,
    20: 0.65,  21: 0.80,  22: 0.92,  23: 0.98,
}


# ──────────────────────────────────────────────────────────────────────────────
# 1. TOMTOM API CALLER
# ──────────────────────────────────────────────────────────────────────────────

def _query_tomtom(lat: float, lon: float, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Query TomTom Flow Segment Data for a single point.
    Returns dict with currentSpeed, freeFlowSpeed, confidence, or None on error.
    """
    try:
        resp = requests.get(
            TOMTOM_FLOW_URL,
            params={
                "key": api_key,
                "point": f"{lat},{lon}",
                "unit": "KMPH",
                "thickness": 1,
            },
            timeout=5,
        )
        if resp.status_code == 429:
            log.warning("TomTom rate limit hit — switching to fallback.")
            return None
        resp.raise_for_status()
        data = resp.json()
        fsd = data.get("flowSegmentData", {})
        return {
            "currentSpeed":   fsd.get("currentSpeed", 0),
            "freeFlowSpeed":  fsd.get("freeFlowSpeed", 0),
            "confidence":     fsd.get("confidence", 0),
            "currentTravelTime": fsd.get("currentTravelTime", 0),
            "freeFlowTravelTime": fsd.get("freeFlowTravelTime", 0),
        }
    except Exception as e:
        log.debug("TomTom API call failed for (%.4f, %.4f): %s", lat, lon, e)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# 2. CORRIDOR SAMPLING
# ──────────────────────────────────────────────────────────────────────────────

def _sample_corridor(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    n_samples: int = 12,
    buffer_deg: float = 0.02,
) -> List[Tuple[float, float]]:
    """
    Generate a grid of sample points in the bounding box around the
    origin-destination corridor, padded by buffer_deg (~2 km).
    """
    min_lat = min(lat1, lat2) - buffer_deg
    max_lat = max(lat1, lat2) + buffer_deg
    min_lon = min(lon1, lon2) - buffer_deg
    max_lon = max(lon1, lon2) + buffer_deg

    # Compute grid dimensions to get ~n_samples points
    aspect = (max_lon - min_lon) / max(max_lat - min_lat, 0.001)
    n_rows = max(2, int(np.sqrt(n_samples / max(aspect, 0.1))))
    n_cols = max(2, int(n_samples / n_rows))

    lats = np.linspace(min_lat, max_lat, n_rows)
    lons = np.linspace(min_lon, max_lon, n_cols)

    points = []
    for lat in lats:
        for lon in lons:
            points.append((lat, lon))

    return points[:n_samples]


# ──────────────────────────────────────────────────────────────────────────────
# 3. FALLBACK HEURISTIC MODEL
# ──────────────────────────────────────────────────────────────────────────────

def _heuristic_speed_ratio(highway_type: str, hour: int) -> float:
    """
    Estimate speed_ratio (current/free_flow) from road type and time of day.
    Returns float in [0.2, 1.0].
    """
    # Normalise highway type (OSMnx sometimes returns lists)
    if isinstance(highway_type, list):
        highway_type = highway_type[0] if highway_type else "residential"

    base = _BASE_RATIO.get(str(highway_type).lower(), 0.85)
    peak_mult = _PEAK_MULTIPLIER.get(hour, 0.90)
    return max(base * peak_mult, 0.20)


# ──────────────────────────────────────────────────────────────────────────────
# 4. FETCH TRAFFIC FOR A CORRIDOR
# ──────────────────────────────────────────────────────────────────────────────

def get_traffic_for_corridor(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    n_samples: int = 12,
) -> Dict[str, Any]:
    """
    Returns traffic data for the origin-destination corridor.

    Result dict:
        source         - "tomtom" or "heuristic"
        speed_ratios   - list of {lat, lon, speed_ratio, current_speed, free_flow_speed}
        kdtree         - cKDTree over sample points for nearest-neighbor lookup
        avg_ratio      - average speed ratio across all samples
        timestamp      - when data was fetched
    """
    # ── check cache ───────────────────────────────────────────────────────────
    cache_key = f"{lat1:.3f},{lon1:.3f}:{lat2:.3f},{lon2:.3f}"
    now = time.time()
    if cache_key in _traffic_cache:
        cached = _traffic_cache[cache_key]
        if now - cached["_ts"] < _CACHE_TTL_SECONDS:
            log.info("Traffic cache hit (age %.0fs)", now - cached["_ts"])
            return cached

    api_key = os.getenv("TOMTOM_KEY", "").strip()
    sample_points = _sample_corridor(lat1, lon1, lat2, lon2, n_samples)

    if api_key:
        # ── try TomTom API ────────────────────────────────────────────────────
        log.info("Fetching traffic from TomTom for %d sample points...", len(sample_points))
        speed_ratios = []
        api_failures = 0

        # Parallelize TomTom API calls — 12 sequential HTTP calls (~6s) become parallel (~1s)
        from concurrent.futures import ThreadPoolExecutor as _TPool, as_completed

        # Expected speed limits for Indian urban roads. TomTom's freeFlowSpeed for Chennai
        # is often 25-34 km/h because it bakes chronic congestion into its baseline.
        # We compare currentSpeed against BOTH freeFlowSpeed AND expected city speed (~40 km/h)
        # to detect real congestion that TomTom's ratio misses.
        EXPECTED_CITY_SPEED = 40.0  # km/h — typical speed limit on Chennai arterials

        def _fetch_point(lat_lon):
            lat, lon = lat_lon
            result = _query_tomtom(lat, lon, api_key)
            if result and result["freeFlowSpeed"] > 0:
                # TomTom ratio: currentSpeed / freeFlowSpeed
                tt_ratio = result["currentSpeed"] / result["freeFlowSpeed"]
                # Absolute ratio: currentSpeed / expected city speed
                abs_ratio = result["currentSpeed"] / EXPECTED_CITY_SPEED
                # Use the LOWER of the two — catches both TomTom-detected AND
                # chronic congestion that TomTom normalizes into its baseline
                effective_ratio = min(tt_ratio, abs_ratio)
                return {
                    "lat": lat, "lon": lon,
                    "speed_ratio": round(min(max(effective_ratio, 0.15), 1.0), 3),
                    "current_speed": result["currentSpeed"],
                    "free_flow_speed": result["freeFlowSpeed"],
                }
            else:
                return None

        with _TPool(max_workers=6) as pool:
            futures = {pool.submit(_fetch_point, pt): pt for pt in sample_points}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    speed_ratios.append(result)
                else:
                    api_failures += 1
                    lat, lon = futures[future]
                    speed_ratios.append({
                        "lat": lat, "lon": lon,
                        "speed_ratio": 0.70,
                        "current_speed": 0,
                        "free_flow_speed": 0,
                    })

        if api_failures > len(sample_points) * 0.5:
            log.warning(
                "TomTom API failed for %d/%d points — switching to full heuristic.",
                api_failures, len(sample_points)
            )
            return _build_heuristic_result(sample_points, cache_key, now)

        source = "tomtom"
    else:
        log.info("No TOMTOM_KEY set — using time-of-day heuristic model.")
        return _build_heuristic_result(sample_points, cache_key, now)

    # ── build KDTree for fast edge→sample lookup ──────────────────────────────
    coords = np.array([(s["lat"], s["lon"]) for s in speed_ratios])
    tree = cKDTree(coords)
    avg_ratio = np.mean([s["speed_ratio"] for s in speed_ratios])

    result = {
        "source": source,
        "speed_ratios": speed_ratios,
        "kdtree": tree,
        "avg_ratio": round(float(avg_ratio), 3),
        "timestamp": datetime.now().isoformat(),
        "n_samples": len(speed_ratios),
        "_ts": now,
    }
    _traffic_cache[cache_key] = result
    log.info(
        "Traffic data ready: source=%s, avg_ratio=%.2f, samples=%d",
        source, avg_ratio, len(speed_ratios)
    )
    return result


def _build_heuristic_result(
    sample_points: List[Tuple[float, float]],
    cache_key: str,
    now: float,
) -> Dict[str, Any]:
    """Build traffic result using time-of-day heuristic (no API needed)."""
    hour = datetime.now().hour
    # Use a "generic arterial road" as the default road type
    generic_ratio = _heuristic_speed_ratio("primary", hour)

    speed_ratios = []
    for lat, lon in sample_points:
        # Slight random variation to avoid all edges having identical traffic
        jitter = np.random.uniform(-0.05, 0.05)
        ratio = max(0.20, min(1.0, generic_ratio + jitter))
        speed_ratios.append({
            "lat": lat,
            "lon": lon,
            "speed_ratio": round(ratio, 3),
            "current_speed": 0,
            "free_flow_speed": 0,
        })

    coords = np.array([(s["lat"], s["lon"]) for s in speed_ratios])
    tree = cKDTree(coords)
    avg_ratio = np.mean([s["speed_ratio"] for s in speed_ratios])

    result = {
        "source": "heuristic",
        "speed_ratios": speed_ratios,
        "kdtree": tree,
        "avg_ratio": round(float(avg_ratio), 3),
        "timestamp": datetime.now().isoformat(),
        "n_samples": len(speed_ratios),
        "_ts": now,
    }
    _traffic_cache[cache_key] = result
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 5. APPLY TRAFFIC TO GRAPH EDGES
# ──────────────────────────────────────────────────────────────────────────────

def apply_traffic_to_graph(
    G,
    traffic_data: Dict[str, Any],
) -> None:
    """
    Set `traffic_factor` on every edge in G based on the nearest traffic sample.

    traffic_factor = speed_ratio (0.2–1.0)
        1.0 = free flow  →  no penalty
        0.5 = 50% of free-flow speed  →  double the effective travel time
        0.2 = severe congestion  →  5x travel time

    This modifies G in-place for maximum performance.
    """
    tree = traffic_data["kdtree"]
    ratios = traffic_data["speed_ratios"]
    ratio_values = np.array([s["speed_ratio"] for s in ratios])

    # Pre-extract all edge midpoints for batch KDTree query
    edges = list(G.edges(keys=True))
    midpoints = []
    for u, v, k in edges:
        y1, x1 = G.nodes[u]["y"], G.nodes[u]["x"]
        y2, x2 = G.nodes[v]["y"], G.nodes[v]["x"]
        midpoints.append(((y1 + y2) / 2, (x1 + x2) / 2))

    pts = np.array(midpoints)
    _, indices = tree.query(pts, k=1)

    # Vectorised assignment
    for i, (u, v, k) in enumerate(edges):
        G[u][v][k]["traffic_factor"] = float(ratio_values[indices[i]])


def get_edge_traffic_factor(G, u: int, v: int, key: int = 0) -> float:
    """Safely read traffic_factor from an edge. Defaults to 0.85 (light traffic)."""
    return G[u][v][key].get("traffic_factor", 0.85)
