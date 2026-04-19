import { useState } from 'react'
import axios from 'axios'
import SearchBox from './SearchBox.jsx'

export default function TopBar({
  origin, dest, setOrigin, setDest,
  alpha, setAlpha,
  carrier, setCarrier,
  weather, weatherLoading,
  onFindRoutes, routesLoading,
  onEmergency, onReroute,
  routes = [],
  showHeatmap = false,
  onToggleHeatmap,
  heatmapLoading = false,
  showTowers = false,
  onToggleTowers,
  towersLoading = false,
  isImmersive = false,
  onToggleImmersive,
}) {
  const handleSlider = (e) => setAlpha(parseFloat(e.target.value))

  const handleDownloadReport = async () => {
    try {
      const routePayload = routes.map(r => ({
        name: r.properties?.name,
        eta_min: r.properties?.eta_min,
        score: r.properties?.score,
        dead_zones: r.properties?.dead_zones,
      }))
      const res = await axios.post('/api/report', { routes: routePayload }, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'a_unique_route_report.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('⚠️ Could not generate report — make sure the backend is running.')
    }
  }

  // Weather display
  const weatherIcon = weather?.description === 'Clear' ? '☀️' :
    weather?.description === 'Clouds' ? '☁️' :
    weather?.description === 'Rain' ? '🌧️' : '🌡️'

  const temp = weather ? `${Math.round(weather.temp ?? 32)}°` : '--'

  return (
    <div className="toolbar">
      {/* Title Row */}
      <div className="toolbar-title">
        <h1>📡 A UNIQUE ROUTE</h1>
        <div className="subtitle">Signal-Aware Routing Engine · Chennai</div>
      </div>

      {/* Main Controls Row */}
      <div className="toolbar-content">
        {/* Weather */}
        <div className="weather-chip">
          <span style={{ fontSize: '28px' }}>{weatherIcon}</span>
          <div>
            <div className="temp">{temp}</div>
            <div className="desc">
              {weather?.description || 'Loading...'}<br />
              {weather?.humidity ? `${weather.humidity}% humidity` : ''}
            </div>
          </div>
        </div>

        {/* Live Traffic Status */}
        {routes.length > 0 && (() => {
          const avgRatio = routes[0]?.properties?.avg_traffic_ratio ?? 0.85
          const source = routes[0]?.properties?.traffic_source ?? 'heuristic'
          const trafficIcon = avgRatio >= 0.75 ? '🟢' : avgRatio >= 0.50 ? '🟡' : avgRatio >= 0.30 ? '🟠' : '🔴'
          const trafficLabel = avgRatio >= 0.75 ? 'Free Flow' : avgRatio >= 0.50 ? 'Moderate' : avgRatio >= 0.30 ? 'Heavy' : 'Severe'
          const trafficColor = avgRatio >= 0.75 ? '#22c55e' : avgRatio >= 0.50 ? '#f59e0b' : avgRatio >= 0.30 ? '#f97316' : '#ef4444'
          return (
            <div className="weather-chip" style={{ borderColor: trafficColor + '33' }}>
              <span style={{ fontSize: '24px' }}>🚦</span>
              <div>
                <div className="temp" style={{ color: trafficColor }}>{trafficIcon} {trafficLabel}</div>
                <div className="desc">
                  {Math.round(avgRatio * 100)}% of free flow<br />
                  via {source === 'tomtom' ? 'TomTom Live' : 'Time Model'}
                </div>
              </div>
            </div>
          )
        })()}

        {/* Search Inputs */}
        {/* Search Inputs & Action Buttons Stacked */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1, minWidth: 0 }}>
          <div className="search-section">
            <SearchBox
              label="FROM"
              placeholder="Origin address..."
              onSelect={setOrigin}
              initialValue={origin?.name}
            />
            <span className="search-arrow">→</span>
            <SearchBox
              label="TO"
              placeholder="Destination address..."
              onSelect={setDest}
              initialValue={dest?.name}
            />
          </div>

          {/* Action Buttons */}
          <div className="action-buttons" style={{ justifyContent: 'flex-start' }}>
            <button className="action-btn emergency" onClick={onEmergency}>
              <span className="btn-icon">🚑</span> Emergency
            </button>
            <button className={`action-btn ${isImmersive ? 'heatmap-active' : ''}`} onClick={onToggleImmersive}>
              <span className="btn-icon">🎥</span> App Immersive
            </button>
            <button className="action-btn" onClick={onReroute} disabled={routes.length === 0}>
              <span className="btn-icon">↻</span> Reroute
            </button>
            <button
              className={`action-btn ${showHeatmap ? 'heatmap-active' : ''}`}
              onClick={onToggleHeatmap}
              disabled={heatmapLoading}
            >
              <span className="btn-icon">{heatmapLoading ? '⏳' : '📶'}</span>
              {heatmapLoading ? 'Loading...' : 'Heatmap'}
            </button>
            <button
              className={`action-btn ${showTowers ? 'heatmap-active' : ''}`}
              onClick={onToggleTowers}
              disabled={towersLoading}
            >
              <span className="btn-icon">{towersLoading ? '⏳' : '🗼'}</span>
              {towersLoading ? 'Loading...' : 'Towers'}
            </button>
            <button className="action-btn" onClick={handleDownloadReport}>
              <span className="btn-icon">📄</span> Report
            </button>
          </div>
        </div>

        {/* Carrier + Slider */}
        <div className="controls-row" style={{ flexDirection: 'column', gap: '6px' }}>
          <select
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
            className="carrier-select"
          >
            <option value="all">🌐 All Networks</option>
            <option value="airtel">Airtel</option>
            <option value="jio">Jio</option>
            <option value="vi">Vi (Vodafone Idea)</option>
            <option value="bsnl">BSNL</option>
          </select>

          <div className="slider-wrap">
            <span className="slider-label">Speed</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={alpha}
              onChange={handleSlider}
              style={{ width: '100px' }}
            />
            <span className="slider-label">Signal</span>
          </div>
        </div>

        {/* Find Routes Button */}
        <button
          onClick={onFindRoutes}
          disabled={!origin || !dest || routesLoading}
          className="find-routes-btn"
        >
          {routesLoading ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
              <div className="spinner" />
              Routing...
            </span>
          ) : 'Find Routes →'}
        </button>
      </div>
    </div>
  )
}
