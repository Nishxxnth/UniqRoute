"""
A Unique Route — Cellular Signal-Aware Routing Engine for Chennai, India.
HARMAN Automotive Track | MIT-MAHE Hackathon
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# Load .env before any other imports
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import folium
from streamlit_folium import st_folium
import osmnx as ox
import networkx as nx

from modules.graph_builder import build_graph
from modules.router import get_routes
from modules.visualizer import build_map
from modules.report_gen import generate_pdf
from modules.weather import get_weather

ox.settings.use_cache = True

GROQ_KEY = os.getenv('GROQ_KEY', '').strip()

EMERGENCY_ORIGIN = "Rajiv Gandhi Government General Hospital, Chennai"
EMERGENCY_DEST = "Marina Beach, Chennai"
CHENNAI_CENTER = (13.08, 80.27)


def geocode_place(query: str) -> tuple:
    """Use Nominatim to geocode a place name to (lat, lon)."""
    try:
        import geopandas as gpd
        gdf = gpd.tools.geocode(query, provider='nominatim', timeout=5)
        if not gdf.empty and gdf.geometry.iloc[0] is not None:
            pt = gdf.geometry.iloc[0]
            return (pt.y, pt.x)
    except Exception:
        pass

    # fallback: use OSMnx geocoder
    try:
        lat, lon = ox.geocoder.geocode(query)
        return (lat, lon)
    except Exception:
        return None


def groq_explain(routes_json: str) -> str:
    """Call Groq API to explain route recommendation."""
    if not GROQ_KEY:
        return "⚠️ GROQ_KEY not set in .env — cannot generate AI explanation."

    prompt = (
        f"Given this route: {routes_json}, explain in 2 sentences whether this route "
        f"is suitable for an emergency vehicle dispatcher. Be specific about dead zones and signal scores."
    )
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200
        }
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ AI explanation unavailable: {e}"


st.set_page_config(page_title="A Unique Route", page_icon="📡", layout="wide")
st.title("📡 A Unique Route")
st.markdown("*Cellular Signal-Aware Routing Engine — Chennai, India | HARMAN Automotive Track*")
st.markdown("---")


# ── SIDEBAR ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Route Options")

    origin = st.text_input(
        "Origin",
        value=EMERGENCY_ORIGIN,
        placeholder="Enter origin address...",
    )
    dest = st.text_input(
        "Destination",
        value=EMERGENCY_DEST,
        placeholder="Enter destination address...",
    )

    if st.button("🚑 Emergency Preset", use_container_width=True):
        st.session_state['origin_val'] = EMERGENCY_ORIGIN
        st.session_state['dest_val'] = EMERGENCY_DEST
        st.rerun()

    st.subheader("Speed vs Connectivity (α)")
    alpha = st.slider(
        "α = 1.0 → Fastest  ·  α = 0.0 → Most Connected",
        0.0, 1.0, 0.5, 0.05,
        help="Slide to choose your routing priority. One route is displayed, blending speed and signal coverage.",
    )

    st.markdown("---")

    # ── Signal Visualization ────────────────────────────────────
    st.subheader("🗺️ Signal Visualization")
    viz_mode = 'heatmap'
    st.info("**HeatMap** layers kernel-density heat to show the overall cellular signal landscape.")

    st.markdown("---")

    # ── Live Weather ──────────────────────────────────────────
    st.subheader("🌤️ Live Weather")
    weather = get_weather(lat=13.08, lon=80.27)

    # Compute estimated signal impact
    rain = weather['rain_mm']
    storm = weather['storm_penalty']
    if rain > 5 or storm >= 0.3:
        signal_impact = "🔴 **Heavy** — expect 15-30% signal degradation, more dead zones"
    elif rain > 1 or storm >= 0.1:
        signal_impact = "🟡 **Moderate** — expect 5-15% signal degradation in exposed areas"
    elif rain > 0:
        signal_impact = "🟠 **Mild** — minimal signal impact, <5% degradation"
    else:
        signal_impact = "🟢 **None** — clear conditions, optimal signal propagation"

    st.markdown(
        f"**Condition:** {weather['description'].title()}\n\n"
        f"Humidity: {weather['humidity']}% | Rain: {weather['rain_mm']:.1f} mm/hr\n\n"
        f"Storm Penalty: {weather['storm_penalty']}\n\n"
        f"**Estimated Signal Impact:** {signal_impact}"
    )

    find_routes = st.button("🔍 Find Routes", type="primary", use_container_width=True)

    st.markdown("---")

    # ── Download Report ───────────────────────────────────────
    st.subheader("📄 Download Report")
    if 'routes' in st.session_state:
        if 'pdf_data' not in st.session_state:
            if st.button("📄 Generate PDF Report", use_container_width=True):
                with st.spinner("Generating PDF..."):
                    out_path = generate_pdf(st.session_state['routes'], weather)
                    with open(out_path, 'rb') as f:
                        st.session_state['pdf_data'] = f.read()
                    st.session_state['pdf_path'] = out_path

        if 'pdf_data' in st.session_state:
            st.download_button(
                label="⬇️ Download PDF Report",
                data=st.session_state['pdf_data'],
                file_name="a_unique_route_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    else:
        st.caption("Find routes first to generate a report.")


# ── MAIN AREA ──────────────────────────────────────────────────────────────
@st.cache_resource
def load_graph():
    return build_graph(cache_path='data/graph_cache.pkl')

if 'graph_loaded' not in st.session_state:
    with st.spinner("Loading Chennai road graph (first run downloads from OSM — may take a minute)..."):
        try:
            G, towers_df = load_graph()
            st.session_state['G'] = G
            st.session_state['towers_df'] = towers_df
            st.session_state['graph_loaded'] = True
        except FileNotFoundError:
            st.session_state['graph_loaded'] = False

if not st.session_state.get('graph_loaded', False):
    st.warning(
        "⚠️ `data/chennai_towers.csv` not found.\n\n"
        "**To use real tower data:** Download MCC 404 + 405 CSVs from [opencellid.org](https://opencellid.org), "
        "filter to Chennai bounding box (lat 12.8–13.2, lon 80.1–80.35), "
        "and save as `data/chennai_towers.csv` with columns: `lat, lon, averageSignal, radio`.\n\n"
        "**Demo mode:** 200 synthetic towers will be generated automatically."
    )
    st.stop()

G = st.session_state['G']
towers_df = st.session_state['towers_df']

# Route computation
if find_routes:
    # Clear old PDF when computing new routes
    st.session_state.pop('pdf_data', None)
    st.session_state.pop('pdf_path', None)

    with st.spinner("Geocoding origin & destination..."):
        orig_pt = geocode_place(origin)
        dest_pt = geocode_place(dest)

    if orig_pt is None:
        st.error(f"Could not geocode origin: {origin}")
        st.stop()
    if dest_pt is None:
        st.error(f"Could not geocode destination: {dest}")
        st.stop()

    with st.spinner("Computing route..."):
        try:
            routes = get_routes(G, orig_pt, dest_pt, alpha=alpha)
            # Clear stale AI explanation when route changes
            st.session_state.pop('groq_explain', None)
            st.session_state['routes'] = routes
            st.session_state['orig_pt'] = orig_pt
            st.session_state['dest_pt'] = dest_pt
            st.session_state['last_alpha'] = alpha
        except nx.NetworkXNoPath:
            st.error("⚠️ No path exists between these two locations. They may be separated by unreachable roads or one-way streets. Try different locations.")

# Auto-recompute route when slider (alpha) changes
if (
    'routes' in st.session_state
    and 'orig_pt' in st.session_state
    and st.session_state.get('last_alpha') != alpha
):
    try:
        routes = get_routes(
            G, st.session_state['orig_pt'], st.session_state['dest_pt'], alpha=alpha
        )
        st.session_state['routes'] = routes
        st.session_state['last_alpha'] = alpha
        st.session_state.pop('groq_explain', None)
        st.session_state.pop('pdf_data', None)
        st.session_state.pop('pdf_path', None)
    except nx.NetworkXNoPath:
        st.error("⚠️ No path exists between these two locations. Adjust your route.")

if 'routes' in st.session_state:
    routes = st.session_state['routes']

    route = routes[0]
    score_color = "🟢" if route['score'] >= 60 else "🟡" if route['score'] >= 30 else "🔴"
    dz = route['dead_zones']
    dz_text = "✅ None" if dz == 0 else f"⚠️ {dz} segments"

    st.markdown(f"### 🛣️ {route['name']}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⏱️ ETA", f"{route['eta_min']:.0f} min")
    with col2:
        st.metric(f"{score_color} Signal Score", f"{route['score']:.0f} / 100")
    with col3:
        st.metric("📡 Dead Zones", dz_text)

    st.markdown("---")

    with st.spinner("Rendering map..."):
        route_map = build_map(
            G, routes, towers_df,
            viz_mode=viz_mode,
            center=CHENNAI_CENTER,
            zoom=12,
        )
        st_folium(route_map, width=1400, height=600, )

    st.markdown("---")
    st.subheader("💡 AI Recommendation")

    explain_key = "groq_explain"
    if explain_key not in st.session_state:
        st.session_state[explain_key] = None

    if st.button("Explain this recommendation"):
        routes_json = json.dumps([
            {
                "name": r['name'],
                "eta_min": r['eta_min'],
                "score": r['score'],
                "dead_zones": r['dead_zones'],
            }
            for r in routes
        ])
        with st.spinner("Asking AI..."):
            explanation = groq_explain(routes_json)
        st.session_state[explain_key] = explanation

    if st.session_state.get(explain_key):
        st.info(st.session_state[explain_key])

else:
    st.info("👈 Set origin & destination in the sidebar, then click **Find Routes** to begin.")
    # Show a centred placeholder map
    placeholder_map = folium.Map(location=CHENNAI_CENTER, zoom_start=12, tiles='CartoDB dark_matter')
    st_folium(placeholder_map, width=1400, height=500)