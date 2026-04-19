import { useState, useCallback, useEffect, useRef } from 'react'
import Map from './components/Map.jsx'
import TopBar from './components/TopBar.jsx'
import RouteCards from './components/RouteCards.jsx'
import { useWeather } from './hooks/useWeather.js'
import { useRoutes } from './hooks/useRoutes.js'
import { useHeatmap } from './hooks/useHeatmap.js'
import { useTowers } from './hooks/useTowers.js'

export default function App() {
  const [origin, setOrigin] = useState(null)
  const [dest, setDest] = useState(null)
  const [alpha, setAlpha] = useState(0.5)
  const [selectedRouteIdx, setSelectedRouteIdx] = useState(null)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [showTowers, setShowTowers] = useState(false)
  const [carrier, setCarrier] = useState('all')
  const [isEmergency, setIsEmergency] = useState(false)
  const [isImmersive, setIsImmersive] = useState(false)

  const { weather, loading: weatherLoading } = useWeather()
  const { routes, loading: routesLoading, error, fetchRoutes } = useRoutes()
  const { heatmapData, loading: heatmapLoading } = useHeatmap(carrier, showHeatmap)
  const { towersData, loading: towersLoading } = useTowers(carrier, showTowers)
  const carPositionRef = useRef(null)

  const handleFindRoutes = useCallback(() => {
    if (!origin || !dest) return
    setIsEmergency(false)
    // Backend: 1.0 = Speed, 0.0 = Signal.
    // Frontend Slider: 0 = Speed, 1 = Signal.
    // So we must invert the alpha before fetching.
    const backendAlpha = 1.0 - alpha
    fetchRoutes(origin, dest, backendAlpha, carrier)
  }, [origin, dest, alpha, carrier, fetchRoutes])

  const handleEmergency = useCallback(() => {
    const o = { lat: 13.0604, lon: 80.2496, name: 'Rajiv Gandhi Govt General Hospital' }
    const d = { lat: 13.0500, lon: 80.2824, name: 'Marina Beach Emergency Bay' }
    setOrigin(o)
    setDest(d)
    setIsEmergency(true)
    setAlpha(0.0) // 0.0 on UI slider means Maximum Speed/Fastest Path
    fetchRoutes(o, d, 1.0, carrier, true) // 1.0 on backend means Maximum Speed, true for emergency mode
  }, [carrier, fetchRoutes])

  const handleReroute = useCallback(() => {
    if (!carPositionRef.current || !dest) return
    const currentLoc = {
      lon: carPositionRef.current[0],
      lat: carPositionRef.current[1],
      name: 'Current Vehicle Position'
    }
    setOrigin(currentLoc)
    const backendAlpha = 1.0 - alpha
    fetchRoutes(currentLoc, dest, backendAlpha, carrier)
  }, [dest, alpha, carrier, fetchRoutes])

  // Dynamically select which route the car visualizes based on the slider value
  useEffect(() => {
    if (alpha <= 0.3) {
      setSelectedRouteIdx(0) // Red / Fastest
    } else if (alpha >= 0.7) {
      setSelectedRouteIdx(2) // Green / Most Connected
    } else {
      setSelectedRouteIdx(1) // Blue / Balanced
    }
  }, [alpha])

  return (
    <div className="app-layout">
      {/* ── Top Toolbar ── */}
      <TopBar
        origin={origin}
        dest={dest}
        setOrigin={setOrigin}
        setDest={setDest}
        alpha={alpha}
        setAlpha={setAlpha}
        carrier={carrier}
        setCarrier={setCarrier}
        weather={weather}
        weatherLoading={weatherLoading}
        onFindRoutes={handleFindRoutes}
        routesLoading={routesLoading}
        onEmergency={handleEmergency}
        onReroute={handleReroute}
        routes={routes}
        showHeatmap={showHeatmap}
        onToggleHeatmap={() => setShowHeatmap(h => !h)}
        heatmapLoading={heatmapLoading}
        showTowers={showTowers}
        onToggleTowers={() => setShowTowers(t => !t)}
        towersLoading={towersLoading}
        isImmersive={isImmersive}
        onToggleImmersive={() => setIsImmersive(i => !i)}
      />

      {/* ── Map (fills middle) ── */}
      <div className="map-container">
        <Map
          heatmapData={heatmapData}
          towersData={towersData}
          routes={routes}
          selectedRouteIdx={selectedRouteIdx}
          onRouteSelect={setSelectedRouteIdx}
          showHeatmap={showHeatmap}
          showTowers={showTowers}
          carPositionRef={carPositionRef}
          isEmergency={isEmergency}
          isImmersive={isImmersive}
          isPaused={routesLoading}
        />
        {error && <div className="error-banner">{error}</div>}
      </div>

      {/* ── Bottom Route Cards ── */}
      {routes.length > 0 && (
        <RouteCards
          routes={routes}
          selectedIdx={selectedRouteIdx}
          onSelect={setSelectedRouteIdx}
        />
      )}
    </div>
  )
}