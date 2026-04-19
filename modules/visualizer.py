"""
Folium map builder with dual visualization modes and route polylines.
- HeatMap mode: kernel-density heat circles (fast, overview of signal landscape)
- Segment mode: per-road-segment colored polylines (precise, shows exact dead zones)

Performance: For large graphs (100k+ edges), we avoid iterating all edges.
Instead we sample node pairs directly for speed.
"""

import folium
from folium.plugins import HeatMap
import networkx as nx
import random
import numpy as np


RADIO_COLORS = {
    'NR': '#ff00ff',    # 5G — magenta
    'LTE': '#00aaff',   # LTE — blue
    'UMTS': '#ffaa00',  # UMTS — orange
    'GSM': '#888888',   # GSM — grey
}

# Aggressive limits to keep render under 3 seconds
MAX_HEATMAP_POINTS = 15000
MAX_SEGMENT_POLYLINES = 2000
MAX_TOWER_MARKERS = 300


def _score_color(score: float) -> str:
    """Map connectivity score 0-100 to green/orange/red hex color."""
    if score >= 70:
        return '#2ecc71'   # green — strong signal
    elif score >= 50:
        return '#f39c12'   # orange — moderate signal
    elif score >= 30:
        return '#e67e22'   # dark orange — weak signal
    else:
        return '#e74c3c'   # red — dead zone


def _sample_edges(G, n, seed=42):
    """Fast edge sampling without materializing the full edge list."""
    random.seed(seed)
    nodes = list(G.nodes())
    total_edges = G.number_of_edges()

    if total_edges <= n:
        # Small enough — return all
        return [(u, v, d) for u, v, d in G.edges(data=True)]

    # Sample by picking random edges via node iteration
    sampled = []
    edge_keys = set()
    # Pick random nodes and grab their edges
    random.shuffle(nodes)
    for node in nodes:
        if len(sampled) >= n:
            break
        for u, v, data in G.edges(node, data=True):
            key = (u, v)
            if key not in edge_keys:
                edge_keys.add(key)
                sampled.append((u, v, data))
                if len(sampled) >= n:
                    break
    return sampled


def build_map(
    G: nx.DiGraph,
    routes: list,
    towers_df,
    viz_mode: str = 'heatmap',
    center: tuple = (13.08, 80.27),
    zoom: int = 12,
    show_heatmap: bool = True,
) -> folium.Map:
    """
    Build Folium map with signal visualization, route polylines, and tower markers.

    viz_mode:
        'heatmap'  — Kernel-density heat overlay (fast, ~1-2s render)
        'segments' — Per-road-segment colored polylines (precise, sampled for speed)
        'both'     — Both layers stacked
    """
    m = folium.Map(location=center, zoom_start=zoom, tiles='CartoDB dark_matter')

    # ── Signal Visualization ──────────────────────────────────
    use_heatmap = viz_mode in ('heatmap', 'both')
    use_segments = viz_mode in ('segments', 'both')

    if use_heatmap:
        sampled = _sample_edges(G, MAX_HEATMAP_POINTS, seed=42)
        edge_midpoints = []
        for u, v, data in sampled:
            y1 = G.nodes[u]['y']
            x1 = G.nodes[u]['x']
            y2 = G.nodes[v]['y']
            x2 = G.nodes[v]['x']
            mid_lat = (y1 + y2) / 2
            mid_lon = (x1 + x2) / 2
            score = data.get('connectivity_score', 50)
            edge_midpoints.append([mid_lat, mid_lon, score / 100.0])

        HeatMap(
            edge_midpoints,
            radius=18,
            blur=15,
            max_zoom=15,
            gradient={0.2: '#e74c3c', 0.5: '#f39c12', 0.8: '#2ecc71', 1.0: '#27ae60'},
        ).add_to(m)

    if use_segments:
        sampled = _sample_edges(G, MAX_SEGMENT_POLYLINES, seed=42)
        for u, v, data in sampled:
            score = data.get('connectivity_score', 50)
            color = _score_color(score)
            y1 = G.nodes[u]['y']
            x1 = G.nodes[u]['x']
            y2 = G.nodes[v]['y']
            x2 = G.nodes[v]['x']
            folium.PolyLine(
                [(y1, x1), (y2, x2)],
                color=color,
                weight=2,
                opacity=0.6,
                tooltip=f"Score: {score:.0f}",
            ).add_to(m)

    # ── Route polylines ───────────────────────────────────────
    for route in routes:
        coords = route['coords']
        popup_html = (
            f"<b>{route['name']}</b><br>"
            f"ETA: {route['eta_min']:.0f} min<br>"
            f"Score: {route['score']:.0f}<br>"
            f"Dead Zones: {route['dead_zones']}"
        )
        folium.PolyLine(
            coords,
            color=route['color'],
            weight=5,
            opacity=0.85,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=route['name'],
        ).add_to(m)

    # ── Tower markers (limited) ───────────────────────────────
    total_towers = len(towers_df)
    if total_towers > MAX_TOWER_MARKERS:
        tower_indices = random.sample(range(total_towers), MAX_TOWER_MARKERS)
        tower_subset = towers_df.iloc[tower_indices]
    else:
        tower_subset = towers_df

    for _, tower in tower_subset.iterrows():
        radio = str(tower.get('radio', 'UNKNOWN')).upper()
        color = RADIO_COLORS.get(radio, '#cccccc')
        folium.CircleMarker(
            location=[tower['lat'], tower['lon']],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            tooltip=f"{radio} | {tower['averageSignal']:.0f} dBm",
        ).add_to(m)

    return m