"""
A Unique Route — Signal Model v2

Realistic signal scoring with proper distance decay and dead zone detection.

Only spatially-varying factors (RSSI, distance, network type) determine per-edge
base scores. Environmental factors (weather, congestion) apply as global
multipliers so they reduce scores uniformly without masking real dead zones.
"""

import numpy as np
from scipy.spatial import KDTree
from typing import List, Tuple, Dict, Any, Optional
import math


# ── Constants ─────────────────────────────────────────────

# Approximate degree-to-km factor at Chennai (~13°N latitude)
DEG_TO_KM = 111.0

# Per-edge factor weights
W = {
    "rssi": 0.30,
    "distance": 0.35,
    "network": 0.20,
    "terrain": 0.15,
}

NETWORK_SCORES = {
    "NR": 100,
    "5G": 100,
    "LTE": 80,
    "UMTS": 50,
    "GSM": 20,
    "UNKNOWN": 40,
}

DEAD_ZONE_THRESHOLD = 30

# Distance decay rate (km⁻¹) — higher = sharper drop
# At rate=3: ~74% at 100m, ~22% at 500m, ~5% at 1km, ~0.2% at 2km
DIST_DECAY_RATE = 3.0


# ── KDTree Builder (IMPORTANT: build once) ─────────────────

def build_kdtree(towers_df):
    """Build a KDTree from tower lat/lon for fast nearest-neighbor lookups."""
    coords = towers_df[['lat', 'lon']].values
    return KDTree(coords)


# ── Factor Functions ───────────────────────────────────────

def factor_rssi(rssi: Optional[float], dist_km: float) -> float:
    """Map measured RSSI (dBm) to 0–100 score, attenuated by distance.
    -110 dBm → 0 score, -50 dBm → 100 score. Signal drops 20 dBm per km."""
    base_rssi = rssi if rssi is not None else -90.0
    # Simulate Free Space Path Loss (FSPL) approximation
    effective_rssi = base_rssi - (dist_km * 20.0)
    return float(np.clip((effective_rssi + 110) / 60 * 100, 0, 100))

def factor_distance(dist_deg: float) -> float:
    """Inverse-square decay with distance from nearest tower.
    Returns near 100 at the tower, dropping off geometrically."""
    dist_km = dist_deg * DEG_TO_KM
    # Inverse-square falloff: 1 / (1 + (d/scale)^2)
    # Using 0.5 km as the half-power scale distance
    scale = 0.5
    return float(np.clip(100.0 / (1.0 + (dist_km / scale)**2), 0, 100))


def factor_network(radio: str) -> float:
    """Map radio tech to a stable baseline score."""
    return float(NETWORK_SCORES.get(radio.upper(), NETWORK_SCORES["UNKNOWN"]))


def factor_terrain(tower_elev: float, road_elev: float) -> float:
    """
    Score Line-Of-Sight Fresnel zone clearance based on topological terrain.
    If a road is deep in a valley relative to the tower, apply a severe penalization.
    """
    # Simple relative Line Of Sight obstruction penalty
    elev_diff = road_elev - tower_elev
    
    # If the car is structurally higher than the tower, signal is completely unobstructed
    if elev_diff >= -5:
        return 100.0
    
    # If the car is deep in a valley / valley street, signal drops exponentially
    # e.g.. diff = -30m -> score = 20
    penalty_score = 100.0 * math.exp(elev_diff / 15.0)
    return float(np.clip(penalty_score, 0, 100))


def environmental_multiplier(weather: Dict[str, Any], hour: int) -> float:
    """Global environmental penalty applied uniformly to all edges.
    Returns a multiplier between 0.5 and 1.0.
    This ensures weather and congestion degrade signal quality
    without masking spatial variation between edges."""
    mult = 1.0

    rain = weather.get("rain_mm", 0)
    humidity = weather.get("humidity", 70)
    storm = weather.get("storm_penalty", 0)

    if rain > 5 or storm >= 0.3:
        mult *= 0.70
    elif rain > 1 or storm >= 0.1:
        mult *= 0.85
    elif rain > 0:
        mult *= 0.95

    if humidity > 90:
        mult *= 0.95

    # Peak congestion hours
    if 17 <= hour <= 20:
        mult *= 0.85
    elif 8 <= hour <= 10:
        mult *= 0.90

    return max(mult, 0.5)


# ── Core Single Score ──────────────────────────────────────

def compute_signal_score(
    point: Tuple[float, float],
    towers_df,
    kdtree: KDTree,
    weather: Dict[str, Any],
    time_of_day: int,
    obstacle_density: int = 5,
) -> Dict[str, Any]:
    """Compute detailed signal score for a single point with full breakdown."""

    lat, lon = point
    dist, idx = kdtree.query([lat, lon], k=1)
    tower = towers_df.iloc[idx]

    rssi_val = tower.get("averageSignal", None)
    radio = tower.get("radio", "UNKNOWN")

    dist_km = dist * DEG_TO_KM
    road_elev = point[2] if len(point) > 2 else 5.0
    tower_elev = tower.get("elevation", 10.0)

    f = {
        "rssi": factor_rssi(rssi_val, dist_km),
        "distance": factor_distance(dist),
        "network": factor_network(radio),
        "terrain": factor_terrain(tower_elev, road_elev)
    }

    base_score = sum(f[k] * W[k] for k in f)
    env_mult = environmental_multiplier(weather, time_of_day)
    score = base_score * env_mult

    return {
        "score": round(score, 2),
        "is_dead_zone": score < DEAD_ZONE_THRESHOLD,
        "breakdown": {k: round(v, 2) for k, v in f.items()},
        "env_multiplier": round(env_mult, 3),
    }


# ── Batch Scoring (FAST) ───────────────────────────────────

def batch_score_segments(
    points: List[Tuple[float, float]],
    towers_df,
    kdtree: KDTree,
    weather: Dict[str, Any],
    time_of_day: int,
    obstacle_density: int = 5,
) -> List[Dict[str, Any]]:
    """Batch-score a list of (lat, lon) midpoints. Returns detailed dicts."""

    if not points:
        return []

    pts_2d = np.array([[p[0], p[1]] for p in points])
    dists, indices = kdtree.query(pts_2d, k=1)

    env_mult = environmental_multiplier(weather, time_of_day)

    scores = []
    for idx_in_points, (dist, idx) in enumerate(zip(dists, indices)):
        tower = towers_df.iloc[idx]

        rssi_val = tower.get("averageSignal", None)
        radio = tower.get("radio", "UNKNOWN")
        road_elev = points[idx_in_points][2] if len(points[idx_in_points]) > 2 else 5.0
        tower_elev = tower.get("elevation", 10.0)

        dist_km = dist * DEG_TO_KM
        f_rssi = factor_rssi(rssi_val, dist_km)
        f_dist = factor_distance(dist)
        f_net = factor_network(radio)
        f_ter = factor_terrain(tower_elev, road_elev)

        base_score = (
            f_rssi * W["rssi"] +
            f_dist * W["distance"] +
            f_net * W["network"] +
            f_ter * W["terrain"]
        )
        score = float(np.clip(base_score * env_mult, 0, 100))
        
        scores.append({
            "score": score,
            "factors": {
                "rssi": round(f_rssi, 1),
                "distance": round(f_dist, 1),
                "network": round(f_net, 1),
                # env_mult is a global multiplier (0.5–1.0); shown as 0–100 for the popup bar
                "weather": round(env_mult * 100, 1),
                # obstacle_density is a constant placeholder (no per-edge OSM query yet)
                "obstacles": round(obstacle_density * 10, 1),
                # congestion duplicates env_mult — both weather & hour contribute to env_mult
                # kept separate in the popup for clarity, marked with same source
                "congestion": round(env_mult * 100, 1),
            }
        })

    return scores