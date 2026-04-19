"""
Build Chennai drivable road graph from OSMnx, annotate with connectivity scores.
"""

import os
import pickle
import pandas as pd
import osmnx as ox
import networkx as nx
from datetime import datetime
from modules.signal_model import build_kdtree, batch_score_segments, DEAD_ZONE_THRESHOLD
from modules.weather import get_weather

ox.settings.use_cache = True
# Enable osmnx verbose logging so users can see download progress in terminal
ox.settings.log_console = True

SYNTHETIC_TOWERS_COLS = ['lat', 'lon', 'averageSignal', 'radio', 'airtel', 'bsnl', 'jio', 'vi']
CARRIERS = ['all', 'airtel', 'bsnl', 'jio', 'vi']


def _generate_synthetic_towers(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate n synthetic towers in Chennai bounding box."""
    import numpy as np
    np.random.seed(seed)
    lat_min, lat_max = 12.8, 13.2
    lon_min, lon_max = 80.1, 80.35

    radios = ['GSM', 'UMTS', 'LTE', 'LTE', 'LTE', 'NR', 'NR']
    rows = []
    for _ in range(n):
        rows.append({
            'lat': np.random.uniform(lat_min, lat_max),
            'lon': np.random.uniform(lon_min, lon_max),
            'averageSignal': np.random.uniform(-90, -60),
            'radio': radios[np.random.randint(0, len(radios))],
            'airtel': True, 'bsnl': True, 'jio': True, 'vi': True
        })
    return pd.DataFrame(rows, columns=SYNTHETIC_TOWERS_COLS)


def _apply_terrain_data(G: nx.DiGraph):
    """
    Simulate a topological heightmap for Chennai (e.g. St Thomas Mount)
    to calculate Line-Of-Sight radio obstructions.
    """
    import math
    print("Applying 3D Terrain Data to Graph Nodes...")
    # St Thomas Mount peak
    mount_lat, mount_lon = 13.003, 80.194
    mount_peak_m = 90.0 # meters high

    for node, data in G.nodes(data=True):
        lat, lon = data['y'], data['x']
        # Distance squared to mount
        dist_sq = (lat - mount_lat)**2 + (lon - mount_lon)**2
        # Gaussian heightmap dropoff
        elevation = mount_peak_m * math.exp(-dist_sq / 0.0005) 
        # Base sea level noise
        elevation += max(2.0, math.sin(lat*100) * 5.0)
        data['elevation'] = elevation
    return G

def _edge_midpoint(G: nx.DiGraph, u: int, v: int) -> tuple:
    """Return (lat, lon, elevation) midpoint of edge u-v."""
    y1 = G.nodes[u]['y']
    x1 = G.nodes[u]['x']
    e1 = G.nodes[u].get('elevation', 5.0)
    y2 = G.nodes[v]['y']
    x2 = G.nodes[v]['x']
    e2 = G.nodes[v].get('elevation', 5.0)
    return ((y1 + y2) / 2, (x1 + x2) / 2, (e1 + e2) / 2)


def build_graph(cache_path: str = 'data/graph_cache.pkl') -> tuple:
    """
    Download/build Chennai drive graph, annotate each edge with connectivity_score.
    Returns (G, towers_df). Caches graph topology to cache_path.

    IMPORTANT: topology (nodes + OSM edges) is cached, but carrier scores are
    always recomputed from towers CSV so switching datasets is reflected immediately.
    """
    # Ensure data dir exists
    os.makedirs(os.path.dirname(cache_path) or '.', exist_ok=True)

    # Load towers
    towers_path = 'data/chennai_towers.csv'
    if os.path.exists(towers_path):
        towers_df = pd.read_csv(towers_path)
        required = set(SYNTHETIC_TOWERS_COLS)
        if towers_df.empty or not required.issubset(towers_df.columns):
            raise ValueError(
                f"data/chennai_towers.csv is missing required columns. "
                f"Expected at minimum: {SYNTHETIC_TOWERS_COLS}. "
                f"Got: {list(towers_df.columns)}"
            )
        # Keep only the columns we need to avoid downstream issues
        towers_df = towers_df[SYNTHETIC_TOWERS_COLS]
        # Ensure carrier booleans are actual bools
        for c in ['airtel', 'bsnl', 'jio', 'vi']:
            if c in towers_df.columns:
                towers_df[c] = towers_df[c].fillna(False).astype(bool)
        print(f"Loaded {len(towers_df)} towers from CSV")
    else:
        towers_df = _generate_synthetic_towers(200)
        print(f"data/chennai_towers.csv not found — generated 200 synthetic towers for demo")

    # Load or build OSM topology (the slow part — downloading from OpenStreetMap)
    topo_cache = cache_path.replace('.pkl', '_topo.pkl')
    if os.path.exists(topo_cache):
        print("Loading cached road topology...")
        with open(topo_cache, 'rb') as f:
            G = pickle.load(f)
        print(f"Loaded cached topology with {G.number_of_edges()} edges")
    else:
        print("Downloading Chennai wider-suburban road graph from OSMnx...")
        # A 25km radius circle covers Ambattur, Kelambakkam, and the entire broader metro!
        G = ox.graph_from_point((13.04, 80.20), dist=25000, network_type="drive")
        print("Extracting largest strongly connected component...")
        G = ox.truncate.largest_component(G, strongly=True)
        G = ox.distance.add_edge_lengths(G)
        print(f"Downloaded graph with {G.number_of_edges()} edges")
        with open(topo_cache, 'wb') as f:
            pickle.dump(G, f)
        print(f"Saved road topology to {topo_cache}")

    G = _apply_terrain_data(G)

    # Check if the fully-annotated graph cache already exists — skip annotation entirely!
    if os.path.exists(cache_path):
        print(f"Loading fully-annotated graph from cache (fast boot)...")
        with open(cache_path, 'rb') as f:
            G = pickle.load(f)
        print(f"Ready! Loaded {G.number_of_edges()} annotated edges instantly.")
        return G, towers_df

    # ── Vectorized Edge Annotation ──────────────────────────────────────────────
    # Build KDTrees per carrier
    print("Building per-carrier KDTrees...")
    kdtrees = {}
    sub_dfs = {}
    tower_coords = {}
    rssi_arr = {}
    radio_arr = {}

    for c in CARRIERS:
        if c == 'all':
            sub_dfs[c] = towers_df
        else:
            if c in towers_df.columns:
                mask = towers_df[c].fillna(False).astype(bool)
                sub_dfs[c] = towers_df[mask]
            else:
                sub_dfs[c] = pd.DataFrame(columns=towers_df.columns)

        if len(sub_dfs[c]) > 0:
            kdtrees[c] = build_kdtree(sub_dfs[c])
            tower_coords[c] = sub_dfs[c][['lat', 'lon']].values
            rssi_arr[c] = sub_dfs[c]['averageSignal'].fillna(-90).values.astype(float)
            radio_arr[c] = sub_dfs[c]['radio'].fillna('UNKNOWN').values
            print(f"  {c}: {len(sub_dfs[c])} towers")
        else:
            kdtrees[c] = None
            print(f"  {c}: NO towers (will score 0)")

    weather = get_weather()
    hour = datetime.now().hour
    import numpy as np
    from modules.signal_model import (
        factor_rssi, factor_distance, factor_network, factor_terrain,
        environmental_multiplier, W, DEAD_ZONE_THRESHOLD, DEG_TO_KM, NETWORK_SCORES
    )

    print(f"Annotating {G.number_of_edges()} edges (vectorized)... (weather: {weather['description']}, hour={hour})")

    # Extract all edge midpoints as a NumPy array in one shot
    edges_list = list(G.edges(keys=True))
    n = len(edges_list)

    mid_y = np.array([(G.nodes[u]['y'] + G.nodes[v]['y']) / 2 for u, v, k in edges_list])
    mid_x = np.array([(G.nodes[u]['x'] + G.nodes[v]['x']) / 2 for u, v, k in edges_list])
    mid_e = np.array([(G.nodes[u].get('elevation', 5.0) + G.nodes[v].get('elevation', 5.0)) / 2 for u, v, k in edges_list])
    pts_2d = np.column_stack([mid_y, mid_x])  # shape (N, 2)

    env_mult = environmental_multiplier(weather, hour)

    # Score each carrier fully vectorized
    all_scores_np = {}
    # Store per-factor arrays for the 'all' carrier (used in popup breakdown)
    all_factors = {}

    for c in CARRIERS:
        if kdtrees[c] is None:
            all_scores_np[c] = np.zeros(n, dtype=float)
            continue

        dists, idxs = kdtrees[c].query(pts_2d, k=1)  # dists shape (N,)
        dist_km = dists * DEG_TO_KM

        # Vectorized RSSI factor: effective_rssi = rssi - dist_km*20; mapped to 0-100
        rssi_vals = rssi_arr[c][idxs]
        eff_rssi = rssi_vals - (dist_km * 20.0)
        f_rssi_v = np.clip((eff_rssi + 110) / 60 * 100, 0, 100)

        # Vectorized distance factor: inverse square
        scale = 0.3
        f_dist_v = np.clip(100.0 / (1.0 + (dist_km / scale) ** 2), 0, 100)

        # Vectorized network factor
        radios = radio_arr[c][idxs]
        f_net_v = np.array([NETWORK_SCORES.get(str(r).upper(), 40) for r in radios], dtype=float)

        # Vectorized terrain factor
        tower_elev_v = np.full(n, 10.0)  # towers at ~10m elevation
        elev_diff = mid_e - tower_elev_v
        f_ter_v = np.where(
            elev_diff >= -5,
            100.0,
            np.clip(100.0 * np.exp(elev_diff / 15.0), 0, 100)
        )

        base = (f_rssi_v * W['rssi'] + f_dist_v * W['distance'] +
                f_net_v * W['network'] + f_ter_v * W['terrain'])
        scores = np.clip(base * env_mult, 0, 100)
        all_scores_np[c] = scores

        # Save individual factor arrays for the 'all' carrier
        if c == 'all':
            all_factors = {
                'rssi': f_rssi_v,
                'distance': f_dist_v,
                'network': f_net_v,
                'obstacles': f_ter_v,  # terrain = obstacles in popup terminology
            }

    # Write scores back to graph
    for idx, (u, v, k) in enumerate(edges_list):
        for c in CARRIERS:
            score_val = float(all_scores_np[c][idx])
            prefix = f"{c}_" if c != "all" else ""
            G[u][v][k][f'{prefix}connectivity_score'] = score_val
            G[u][v][k][f'{prefix}is_dead_zone'] = score_val < DEAD_ZONE_THRESHOLD
        # Store individual factor breakdowns from 'all' carrier for popup
        G[u][v][k]['factor_rssi'] = round(float(all_factors['rssi'][idx]), 1)
        G[u][v][k]['factor_distance'] = round(float(all_factors['distance'][idx]), 1)
        G[u][v][k]['factor_network'] = round(float(all_factors['network'][idx]), 1)
        G[u][v][k]['factor_obstacles'] = round(float(all_factors['obstacles'][idx]), 1)
        G[u][v][k]['factor_weather'] = round(env_mult * 100, 1)
        G[u][v][k]['factor_congestion'] = round(env_mult * 100, 1)  # same as weather (both from env_mult)

    print(f"Annotated {n} edges for {len(CARRIERS)} carrier profiles")

    # Save fully-annotated graph to cache — next boot will skip annotation entirely!
    with open(cache_path, 'wb') as f:
        pickle.dump(G, f)
    print(f"Saved annotated graph to {cache_path} (future boots will skip annotation)")

    return G, towers_df