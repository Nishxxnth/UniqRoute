"""
A Unique Route FastAPI server — wraps existing modules as REST endpoints.
"""

from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import io
import json

load_dotenv()

from modules.graph_builder import build_graph
from modules.router import get_routes, stamp_blended_weights, invalidate_stamped_weights
from modules.weather import get_weather
from modules.report_gen import generate_pdf
from modules.traffic import get_traffic_for_corridor, apply_traffic_to_graph

# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

G = None
towers_df = None
HEATMAP_CACHE = {}
TOWERS_CACHE = {}
_last_traffic_ts: str = ""  # timestamp of last traffic application to skip redundant re-application

# Thread pool for CPU-bound tasks — enough workers for 3 parallel A* + traffic + cache builds
_executor = ThreadPoolExecutor(max_workers=6)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global G, towers_df
    G, towers_df = build_graph(cache_path="cache/graph_cache.pkl")

    # Kick off cache warming in the background — server is ready immediately.
    # The 'all' carrier cache (most common) is warmed first, then the rest.
    async def _warm_caches():
        loop = asyncio.get_event_loop()
        carriers = ["all", "airtel", "bsnl", "jio", "vi"]
        print("Background cache warming started...")
        for carrier in carriers:
            await loop.run_in_executor(_executor, _build_heatmap, carrier)
            await loop.run_in_executor(_executor, _build_towers, carrier)
            print(f"  ✓ Cache warmed: {carrier}")
        print(f"All caches warmed ({len(HEATMAP_CACHE)} heatmap + {len(TOWERS_CACHE)} towers)")

    asyncio.create_task(_warm_caches())

    yield


app = FastAPI(lifespan=lifespan)

# Compress large GeoJSON responses (heatmap/towers) — typically 10x smaller on the wire
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ────────────────────────────────────────────────


class RoutesRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    alpha: float = 0.5
    carrier: str = "all"
    emergency: bool = False

class ReportRequest(BaseModel):
    routes: list = []
    carrier: str = "all"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _route_to_geojson(route: dict) -> dict:
    """Convert route coords from [(lat, lon), ...] to GeoJSON LineString [[lon, lat], ...]."""
    coordinates = [[lon, lat] for lat, lon in route["coords"]]
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {
            "name": route["name"],
            "color": route["color"],
            "eta_min": route["eta_min"],
            "freeflow_eta_min": route.get("freeflow_eta_min", route["eta_min"]),
            "traffic_delay_min": route.get("traffic_delay_min", 0),
            "avg_traffic_ratio": route.get("avg_traffic_ratio", 0.85),
            "distance_km": route.get("distance_km", 0),
            "score": route["score"],
            "dead_zones": route["dead_zones"],
            "dead_zone_segments": route.get("dead_zone_segments", []),
        },
    }


def _build_heatmap(carrier: str) -> bytes:
    """Build and cache heatmap GeoJSON for a single carrier. Called at startup and on-demand."""
    if carrier in HEATMAP_CACHE:
        return HEATMAP_CACHE[carrier]

    prefix = f"{carrier}_" if carrier != "all" else ""
    features = []
    # Sample ~1 in 4 edges to keep GeoJSON manageable for the browser (~100k → ~25k features).
    # Always include edges with very high or very low scores so the map stays accurate.
    for i, (u, v, k, data) in enumerate(G.edges(keys=True, data=True)):
        score = data.get(f"{prefix}connectivity_score", 50)
        # Always include edge if it's notable (very good or very bad), else sample every 4th
        if score < 20 or score > 80 or i % 4 == 0:
            if "geometry" in data:
                coords = list(data["geometry"].coords)
            else:
                y1, x1 = G.nodes[u]["y"], G.nodes[u]["x"]
                y2, x2 = G.nodes[v]["y"], G.nodes[v]["x"]
                coords = [[x1, y1], [x2, y2]]

            features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "connectivity_score": round(score, 1),
                    "score_rssi": round(data.get("factor_rssi", score), 1),
                    "score_distance": round(data.get("factor_distance", score), 1),
                    "score_network": round(data.get("factor_network", score), 1),
                    "score_weather": round(data.get("factor_weather", score), 1),
                    "score_obstacles": round(data.get("factor_obstacles", 50), 1),
                    "score_congestion": round(data.get("factor_congestion", score), 1),
                },
            })

    payload = {"type": "FeatureCollection", "features": features}
    payload_bytes = json.dumps(payload).encode("utf-8")
    HEATMAP_CACHE[carrier] = payload_bytes
    return payload_bytes


def _build_towers(carrier: str) -> bytes:
    """Build and cache cell towers GeoJSON for a single carrier."""
    if carrier in TOWERS_CACHE:
        return TOWERS_CACHE[carrier]

    features = []
    for idx, row in towers_df.iterrows():
        if carrier != "all" and not row.get(carrier, False):
            continue
            
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row['lon'], row['lat']]},
            "properties": {
                "is_tower": True,
                "radio": row.get("radio", "UNKNOWN"),
                "carrier": carrier,
                "averageSignal": row.get("averageSignal", -90)
            }
        })

    payload = {"type": "FeatureCollection", "features": features}
    payload_bytes = json.dumps(payload).encode("utf-8")
    TOWERS_CACHE[carrier] = payload_bytes
    return payload_bytes


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/weather")
async def weather():
    return get_weather(lat=13.08, lon=80.27)


@app.post("/routes")
async def routes(req: RoutesRequest):
    if G is None:
        raise HTTPException(status_code=500, detail="Graph not loaded")

    origin = (req.origin_lat, req.origin_lon)
    dest = (req.dest_lat, req.dest_lon)
    carrier = req.carrier.lower() if req.carrier else "all"

    loop = asyncio.get_event_loop()

    # 1. Fetch live traffic. Only re-apply to graph if traffic data is fresher than last call.
    global _last_traffic_ts
    traffic_data = await loop.run_in_executor(
        _executor,
        get_traffic_for_corridor,
        req.origin_lat, req.origin_lon,
        req.dest_lat, req.dest_lon,
    )
    if traffic_data.get("timestamp", "") != _last_traffic_ts:
        await loop.run_in_executor(
            _executor,
            apply_traffic_to_graph, G, traffic_data,
        )
        _last_traffic_ts = traffic_data.get("timestamp", "")
        invalidate_stamped_weights()  # force re-stamp with new traffic factors

    # 2. Pre-compute nearest nodes ONCE (not 3 times)
    import osmnx as ox_mod
    orig_node = ox_mod.nearest_nodes(G, req.origin_lon, req.origin_lat)
    dest_node = ox_mod.nearest_nodes(G, req.dest_lon, req.dest_lat)

    # 3. Pre-stamp blended weights (skips if already stamped for this alpha/carrier)
    alphas = [1.0] if req.emergency else [1.0, req.alpha, 0.0]
    for a in alphas:
        weight_key = f'_w_{a:.2f}_{carrier}'
        stamp_blended_weights(G, a, carrier, weight_key)

    # 4. Run Dijkstra sequentially (Python GIL makes threading useless for CPU-bound work)
    if req.emergency:
        fast_result = get_routes(G, origin, dest, 1.0, carrier, orig_node, dest_node)
        routes_list = [fast_result[0]]
    else:
        fast_result = get_routes(G, origin, dest, 1.0, carrier, orig_node, dest_node)
        blend_result = get_routes(G, origin, dest, req.alpha, carrier, orig_node, dest_node)
        conn_result = get_routes(G, origin, dest, 0.0, carrier, orig_node, dest_node)
        routes_list = [fast_result[0], blend_result[0], conn_result[0]]

    geojson_routes = [_route_to_geojson(r) for r in routes_list]

    # Attach traffic metadata to the response
    for gj in geojson_routes:
        gj["properties"]["traffic_source"] = traffic_data.get("source", "heuristic")

    return geojson_routes


@app.get("/heatmap")
async def heatmap(carrier: str = "all"):
    if G is None:
        raise HTTPException(status_code=500, detail="Graph not loaded")

    carrier = carrier.lower()
    return Response(content=_build_heatmap(carrier), media_type="application/json")


@app.get("/towers")
async def towers(carrier: str = "all"):
    if G is None:
        raise HTTPException(status_code=500, detail="Graph not loaded")

    carrier = carrier.lower()
    return Response(content=_build_towers(carrier), media_type="application/json")


@app.post("/report")
async def report(req: ReportRequest):
    """
    Generate a PDF report. Accepts optional routes list so the
    Route Comparison table in the PDF is populated with real data.
    """
    weather_data = get_weather(lat=13.08, lon=80.27)
    output_path = generate_pdf(req.routes, weather_data, output_path="a_unique_route_report.pdf")

    # Stream file as bytes so the endpoint works even if FileResponse path is relative
    with open(output_path, "rb") as f:
        pdf_bytes = f.read()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=a_unique_route_report.pdf"},
    )


@app.get("/traffic")
async def traffic(lat1: float = 13.0, lon1: float = 80.2, lat2: float = 13.1, lon2: float = 80.3):
    """
    Return live traffic data for a corridor.
    Used by the React frontend to show traffic status.
    """
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        _executor,
        get_traffic_for_corridor,
        lat1, lon1, lat2, lon2,
    )
    # Strip non-serializable KDTree before returning to client
    return {
        "source": data["source"],
        "avg_ratio": data["avg_ratio"],
        "n_samples": data["n_samples"],
        "timestamp": data["timestamp"],
        "speed_ratios": data["speed_ratios"],
    }



