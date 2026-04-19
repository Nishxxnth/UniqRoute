# A Unique Route 🚑📶

**A Unique Route** is an advanced, High-Fidelity Signal-Aware Routing Engine designed to optimize navigation not just for speed, but for **network connectivity**. 

Originally conceptualized for Emergency Service Vehicles (Ambulances) where losing network communication in "Dead Zones" can mean a critical failure in transmitting patient vitals to hospitals, this project introduces a dynamic dual-metric routing system built over a highly optimized Geographic Road Network mapped from OSM (OpenStreetMap) and actual Cell-Tower coordinate datasets.

---

## 🌟 The Innovation
Traditional routing algorithms (like those powering Google Maps or Waze) strictly minimize travel time or distance (Fastest Route). A Unique Route introduces **Connectivity as a First-Class Navigation Metric**. 

By physically mapping millions of telecom towers onto a spatial KDTree and continuously evaluating signal strength degradation across 170,000+ individual road segments, the engine provides:
1. **Intelligent Dead-Zone Avoidance:** The engine actively dodges streets with heavy geometric or structural signal blockage if an alternative parallel route exists.
2. **Predictive Pre-Caching:** If a Dead Zone is completely unavoidable, the navigation UI calculates exactly when the vehicle will hit the edge of the zone and executes a `Pre-Cache` alert 500 meters in advance to download local map tiles. 
3. **Immersive Navigation:** A Google-Maps equivalent 3D tracking engine built natively with MapLibre to visually simulate vehicle progression.

---

## 🛠 Mode of Approach & Solution
The solution merges geographic network theory with real-time parametric pathfinding.

1. **Topology Generation:** Using `OSMnx`, the platform extracts the raw physical street network of the target city (Chennai).
2. **Signal Model Scoring:** `signal_model.py` dynamically computes a Connectivity Score (0-100) for every single street by cross-referencing cell tower proximities via KDTree optimization. It processes physical obstruction density and penalizes ranges over 200m heavily using exponential decay models. 
3. **Parametric A* Search:** `router.py` executes a high-performance `A-Star (A*) Search Algorithm`. The user defines an `alpha` parameter (0.0 to 1.0) on the UI Slider. 
   - Weight Function: `Cost = (alpha * Traffic_Distance) + ((1 - alpha) * Exponential_Signal_Penalty)`
   - This smoothly blends the routing objective from **Pure Speed** (A to B as fast as possible) to **Pure Connectivity** (Stay safely online at the cost of a slightly longer drive).

---

## 🧩 Architecture

The project is split into a heavily mathematical asynchronous Python backend and a reactive modern Web UI.

### 1. Backend Engine (`FastAPI` & `NetworkX`)
* **`api.py`:** The primary Async HTTP server serving routing, heatmap data, and PDF reports. Runs ThreadPoolExecutors to parallelize Dijkstra/A* computations.
* **`modules/graph_builder.py`:** The offline pipeline. Downloads the city, loads the `towers.csv`, evaluates KDTree distances for millions of edges, calculates the base weights, and produces the `graph_cache.pkl` (an enormous pre-annotated Python object).
* **`modules/router.py`:** The core mathematical brain. Evaluates shortest paths, runs dynamic heuristic functions, detects contiguous dead-zone segments, and computes ETAs.
* **`modules/traffic.py`:** Integrates dynamically with the TomTom Flow API to query live congestion across the route corridor natively.

### 2. Frontend Interface (`React`, `Vite`, `MapLibre GL JS`)
* **Dynamic Simulation (`Map.jsx`):** Employs a 60-FPS `requestAnimationFrame` interpolation engine to animate a vehicle tracking perfectly along geographic vector lines.
* **Cinematic 3D Camera:** Dynamically calculates vectors via `Math.atan2()` to calculate Map bearing and lock the user's viewport right behind the vehicle at a 65° pitch angle.
* **Live Rerouting:** Pauses the animation cycle mid-frame, recalculates origins based on the current hover position of the car, and initiates seamless mid-route swapping.

---

## 🚀 How to Run It

### ⚙️ Prerequisites
- Python 3.9+
- Node.js v18+
- TomTom Developer API Key (for Live Traffic)

### 1. Backend Setup
1. Open a terminal and navigate to the project root:
   ```bash
   cd connectroute
   ```
2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root and add your keys:
   ```env
   TOMTOM_KEY=your_tomtom_api_key_here
   ```
4. Start the FastAPI Engine:
   ```bash
   uvicorn api:app --reload --port 8000
   ```
   *(Note: The very first launch will take roughly 3-5 minutes as `graph_builder.py` physically downloads the city map and pre-computes the 170,000+ route scorings. It caches to `graph_cache.pkl` for instant booting on subsequent launches.)*

### 2. Frontend Setup
1. Open a new terminal tab and navigate into the `frontend` folder:
   ```bash
   cd frontend
   ```
2. Install the React packages:
   ```bash
   npm install
   ```
3. Spin up the Vite development server:
   ```bash
   npm run dev
   ```
4. Open the displayed Localhost URL in your browser (usually `http://localhost:5173`).

---

## 🎮 Usage Guide

- **Normal Routing:** Select a Starting Point and Destination. Adjust the Speed/Signal slider according to your needs, and click "Find Routes". 
- **Emergency Dispatch:** Click the **🚑 Emergency** button. This bypasses the slider, forces `Alpha = 0.0` (Absolute maximum speed routing), and changes the vehicle icon into an Ambulance.
- **3D Navigation tracking:** Once a vehicle is moving, click **🎥 App Immersive**. The viewport will lock onto the rear of the car and follow it into curves actively. Break the lock by dragging the map manually.
- **Dynamic Reroute:** While the car is driving, hit **↻ Reroute**. The vehicle will instantly pause, beam its current coordinates to the backend, and trace a completely new route from its exact location.
