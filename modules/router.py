"""
Router: compute fastest / most-connected / blended routes.
Uses Dijkstra's algorithm with three different cost functions.
"""

import osmnx as ox
import networkx as nx
import math
from typing import List, Dict, Any, Tuple

ox.settings.use_cache = True


def _dist(p1: tuple, p2: tuple) -> float:
    """Cheap squared Euclidean distance between two (lat, lon) points."""
    return (p1[0] - p2[0])**2 + (p1[1] - p2[1])**2


def _first_edge(G, u: int, v: int) -> dict:
    """Return the data dict for the first (or only) edge u->v."""
    edge_data = G.get_edge_data(u, v)
    if edge_data is None:
        return {}
    if isinstance(edge_data, dict):
        # Pick the first key
        first_key = next(iter(edge_data.keys()))
        return edge_data[first_key]
    return edge_data


def _edge_weight_connected(carrier: str = 'all'):
    """Returns a weight function: 1 / (score + 1) — carrier-aware."""
    def weight_fn(u, v, d) -> float:
        min_weight = float('inf')
        prefix = f"{carrier}_" if carrier != "all" else ""
        for key, edge_data in d.items():
            score = edge_data.get(f'{prefix}connectivity_score', 50)
            w = 1.0 / (score + 1)
            if w < min_weight:
                min_weight = w
        return min_weight
    return weight_fn


def _edge_weight_blended(alpha: float, carrier: str = 'all'):
    """Return a weight function for the blended route with given alpha.

    The key design: the two terms measure fundamentally different things:

      distance_term = traffic_length / MEDIAN_LENGTH
          → Scales with road length. A 200m road costs 2x a 100m road.
          → Minimized at alpha=1.0 → produces the FASTEST route.

      signal_term = exp((100 - score) / 25)
          → Per-edge FIXED cost based on signal quality.
          → Does NOT scale with length. A 10m dead-zone road costs the
            same as a 1km dead-zone road (both are equally bad for signal).
          → Minimized at alpha=0.0 → produces the MOST CONNECTED route,
            preferring many short good-signal edges over fewer long bad ones.

    Weight = alpha × distance_term + (1 - alpha) × signal_term

    This ensures alpha=1.0 and alpha=0.0 produce genuinely DIFFERENT paths.
    """
    MEDIAN_LENGTH = 100.0  # metres

    def weight_fn(u, v, d) -> float:
        min_weight = float('inf')
        prefix = f"{carrier}_" if carrier != "all" else ""
        for key, edge_data in d.items():
            length = edge_data.get('length', 100)
            score = edge_data.get(f'{prefix}connectivity_score', 50)

            # Traffic-adjusted distance term (scales with road length)
            traffic_factor = edge_data.get('traffic_factor', 0.85)
            traffic_length = length / max(traffic_factor, 0.15)
            distance_term = traffic_length / MEDIAN_LENGTH

            # Signal quality term
            # Multiply by distance_term so A* heuristic can correctly guide the search space!
            signal_term = math.exp((100 - score) / 25.0) * (distance_term + 0.1)

            w = alpha * distance_term + (1 - alpha) * signal_term
            if w < min_weight:
                min_weight = w
        return min_weight

    return weight_fn


def _route_stats(G, route_nodes: List[int], carrier: str = 'all') -> Dict[str, Any]:
    """Compute ETA, mean score, dead zones, and traffic metrics for a route."""
    total_length = 0.0
    total_weighted_score = 0.0
    dead_zones = 0
    traffic_factors = []
    
    dead_zone_segments = []
    in_dead_zone = False
    current_dz_start_dist = 0.0
    current_dz_length = 0.0
    current_dist = 0.0

    # Accumulate per-edge travel time using traffic-adjusted speeds
    # instead of a flat 30 km/h assumption
    total_freeflow_time_s = 0.0   # time at free-flow speed
    total_traffic_time_s = 0.0    # time at current (congested) speed

    for i in range(len(route_nodes) - 1):
        u = route_nodes[i]
        v = route_nodes[i + 1]
        edata = _first_edge(G, u, v)
        prefix = f"{carrier}_" if carrier != "all" else ""
        length = edata.get('length', 100)  # metres
        score = edata.get(f'{prefix}connectivity_score', 50)
        traffic_factor = edata.get('traffic_factor', 0.85)

        total_length += length
        total_weighted_score += score * length
        traffic_factors.append(traffic_factor)

        is_dz = edata.get(f'{prefix}is_dead_zone', False)
        if is_dz:
            dead_zones += 1
            if not in_dead_zone:
                in_dead_zone = True
                current_dz_start_dist = current_dist
                current_dz_length = length
            else:
                current_dz_length += length
        else:
            if in_dead_zone:
                dead_zone_segments.append({
                    'start_dist_m': round(current_dz_start_dist, 1),
                    'length_m': round(current_dz_length, 1)
                })
                in_dead_zone = False

        # Use OSMnx speed_kph if available, else assume 30 km/h
        speed_kph = edata.get('speed_kph', 30)
        freeflow_speed_ms = speed_kph / 3.6   # km/h → m/s
        current_speed_ms = freeflow_speed_ms * max(traffic_factor, 0.15)

        total_freeflow_time_s += length / freeflow_speed_ms if freeflow_speed_ms > 0 else 0
        total_traffic_time_s += length / current_speed_ms if current_speed_ms > 0 else 0

    eta_min = total_traffic_time_s / 60.0
    freeflow_eta_min = total_freeflow_time_s / 60.0
    traffic_delay_min = max(0, eta_min - freeflow_eta_min)
    avg_traffic_ratio = sum(traffic_factors) / len(traffic_factors) if traffic_factors else 0.85
    mean_score = (total_weighted_score / total_length) if total_length > 0 else 50.0

    if in_dead_zone:
        dead_zone_segments.append({
            'start_dist_m': round(current_dz_start_dist, 1),
            'length_m': round(current_dz_length, 1)
        })

        current_dist += length

    # Build precise route coordinates using actual road geometry from OSMnx.
    # Each edge may have a 'geometry' Shapely LineString with the real road shape.
    # Without this, we'd draw straight lines between nodes that cut through buildings.
    coords = []
    for i in range(len(route_nodes) - 1):
        u = route_nodes[i]
        v = route_nodes[i + 1]
        edge = _first_edge(G, u, v)

        if 'geometry' in edge:
            # Shapely .coords gives (x, y) = (lon, lat); we need (lat, lon)
            edge_pts = [(lat, lon) for lon, lat in edge['geometry'].coords]
            # Check if the geometry runs in the wrong direction (v→u instead of u→v)
            u_coord = (G.nodes[u]['y'], G.nodes[u]['x'])
            if edge_pts and _dist(edge_pts[0], u_coord) > _dist(edge_pts[-1], u_coord):
                edge_pts.reverse()
        else:
            # No geometry — straight line between nodes (short edges only)
            edge_pts = [(G.nodes[u]['y'], G.nodes[u]['x']),
                        (G.nodes[v]['y'], G.nodes[v]['x'])]

        # Avoid duplicate points at junctions
        if coords and edge_pts:
            coords.extend(edge_pts[1:])
        else:
            coords.extend(edge_pts)
            
        current_dist += length

    return {
        'coords': coords,
        'eta_min': round(eta_min, 1),
        'freeflow_eta_min': round(freeflow_eta_min, 1),
        'traffic_delay_min': round(traffic_delay_min, 1),
        'avg_traffic_ratio': round(avg_traffic_ratio, 2),
        'score': round(mean_score, 1),
        'dead_zones': dead_zones,
        'dead_zone_segments': dead_zone_segments,
        'distance_km': round(total_length / 1000.0, 2),
    }


# Track which weight keys have been stamped to skip redundant 400k-edge iterations
_stamped_keys = set()


def stamp_blended_weights(G, alpha: float, carrier: str = 'all', weight_key: str = '_w') -> None:
    """
    Pre-stamp blended weight onto every edge under `weight_key`.

    This replaces the callable weight function with a pre-computed attribute.
    NetworkX's shortest_path with a string weight key uses fast C-level dict 
    lookups instead of calling a Python function per-edge — ~10-30x faster.
    
    Skips stamping if this exact key was already stamped (cached).
    """
    if weight_key in _stamped_keys:
        return  # Already stamped — skip 400k edge iteration
    
    MEDIAN_LENGTH = 100.0
    prefix = f"{carrier}_" if carrier != "all" else ""

    for u, v, k, data in G.edges(keys=True, data=True):
        length = data.get('length', 100)
        score = data.get(f'{prefix}connectivity_score', 50)
        traffic_factor = data.get('traffic_factor', 0.85)

        traffic_length = length / max(traffic_factor, 0.15)
        distance_term = traffic_length / MEDIAN_LENGTH

        signal_term = math.exp((100 - score) / 25.0) * (distance_term + 0.1)

        data[weight_key] = alpha * distance_term + (1 - alpha) * signal_term

    _stamped_keys.add(weight_key)


def invalidate_stamped_weights():
    """Called when traffic data changes — forces re-stamping on next route request."""
    _stamped_keys.clear()


def get_routes(
    G,
    origin_coords: Tuple[float, float],
    dest_coords: Tuple[float, float],
    alpha: float = 0.5,
    carrier: str = 'all',
    orig_node: int = None,
    dest_node: int = None,
) -> List[Dict[str, Any]]:
    """
    Compute a single route between origin and dest based on the alpha blending value.
    α = 1.0 → pure fastest (shortest distance)
    α = 0.0 → pure most-connected (best signal)
    0 < α < 1 → blended trade-off

    Returns list with one route dict (keys: name, color, nodes, coords, eta_min, score, dead_zones).
    """
    if orig_node is None:
        orig_node = ox.nearest_nodes(G, origin_coords[1], origin_coords[0])
    if dest_node is None:
        dest_node = ox.nearest_nodes(G, dest_coords[1], dest_coords[0])

    # Weight key (already pre-stamped on edges by the API layer)
    weight_key = f'_w_{alpha:.2f}_{carrier}'

    # Use Dijkstra with string weight key — C-level dict lookups, much faster than callable
    path = nx.shortest_path(
        G, orig_node, dest_node,
        weight=weight_key
    )
    stats = _route_stats(G, path, carrier)

    # Dynamic naming and color based on alpha position
    # Fastest=Red, Most Connected=Green, Balanced=Blue
    if alpha >= 0.95:
        name, color = 'Fastest', '#e74c3c'
    elif alpha <= 0.05:
        name, color = 'Most Connected', '#22c55e'
    else:
        name = f'Balanced (α={alpha:.2f})'
        color = '#3b82f6'

    route = {
        'name': name,
        'color': color,
        'nodes': path,
        'coords': stats['coords'],
        'eta_min': stats['eta_min'],
        'freeflow_eta_min': stats['freeflow_eta_min'],
        'traffic_delay_min': stats['traffic_delay_min'],
        'avg_traffic_ratio': stats['avg_traffic_ratio'],
        'distance_km': stats['distance_km'],
        'score': stats['score'],
        'dead_zones': stats['dead_zones'],
        'dead_zone_segments': stats['dead_zone_segments'],
    }
    return [route]