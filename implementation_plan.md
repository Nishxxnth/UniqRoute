# Fix Map Performance and Missing Route Lines

The issues described ("towers randomly disappearing", "glitchy", "taking too much time", "missing route lines") are classic symptoms of the map's WebGL context crashing or dropping frames due to an overloaded data source. Currently, both the massive road network (hundreds of thousands of segments) and all cell towers (thousands of points) are bundled into a single GeoJSON source (`HEATMAP_SOURCE`). 

To fix this and fulfill the new requirements, we need to decouple these layers.

## User Review Required

> [!IMPORTANT]
> This plan involves separating the `heatmap` and `towers` data into two different endpoints to prevent the browser from freezing and the WebGL context from crashing. 
> 
> A new "Towers" toggle button will be added to the TopBar, allowing you to show/hide the cell towers completely independently of the heatmap or the route lines.

## Open Questions

None at the moment. This approach safely optimizes the frontend without changing the core routing logic.

## Proposed Changes

### Backend (FastAPI)
#### [MODIFY] `api.py`
- Create a new `TOWERS_CACHE` and pre-warm it during startup.
- Update `_build_heatmap` to **only** return road network edges (LineStrings).
- Create a new `_build_towers` helper to return only the cell towers (Points).
- Add a new `GET /api/towers` endpoint.

### Frontend Hooks
#### [NEW] `frontend/src/hooks/useTowers.js`
- Create a new hook to fetch data from `/api/towers?carrier=...` and manage its state, mirroring how `useHeatmap` works.

### Frontend Components
#### [MODIFY] `frontend/src/App.jsx`
- Introduce a new state `showTowers` (default `false`).
- Integrate the new `useTowers` hook.
- Pass `showTowers`, `towersData`, and a toggle function down to `TopBar` and `Map`.

#### [MODIFY] `frontend/src/components/TopBar.jsx`
- Add a new action button: `📡 Towers` next to the Heatmap button.
- Wire it up to toggle the `showTowers` state.

#### [MODIFY] `frontend/src/components/Map.jsx`
- Initialize a new `TOWERS_SOURCE` (`towers-source`) in maplibre.
- Move the `heatmap-towers` circle layer to use this new `TOWERS_SOURCE` instead of `HEATMAP_SOURCE`.
- Add a new `useEffect` to update `TOWERS_SOURCE` when `towersData` changes.
- Update the visibility toggle to handle `heatmap-towers` using the `showTowers` prop.
- Fix the `ROUTE_SOURCES` naming order to match the backend responses (Fastest, Blended, Connected).

## Verification Plan

### Manual Verification
1. Load the frontend and verify the map renders smoothly without glitching or crashing.
2. Toggle the `Heatmap` button to ensure roads light up correctly based on signal strength.
3. Toggle the new `Towers` button to ensure cell tower markers appear and disappear instantly without affecting routes or the heatmap.
4. Search for a route and verify all 3 route lines (Fastest, Balanced, Most Connected) appear distinctly on the map.
