import { useState } from 'react'
import axios from 'axios'
import SearchBox from './SearchBox.jsx'
import WeatherCard from './WeatherCard.jsx'

const EMERGENCY_ORIGIN = { lat: 13.0604, lon: 80.2496, name: 'Rajiv Gandhi Govt General Hospital' }
const EMERGENCY_DEST = { lat: 13.0500, lon: 80.2824, name: 'Marina Beach Emergency Bay' }

export default function Sidebar({
  origin, dest, setOrigin, setDest,
  alpha, setAlpha,
  carrier, setCarrier,
  weather, weatherLoading,
  onFindRoutes, routesLoading,
  onEmergency,
  routes = [],
  showHeatmap = false,
  onToggleHeatmap,
}) {
  const handleSlider = (e) => setAlpha(parseFloat(e.target.value))

  const handleDownloadReport = async () => {
    try {
      // POST routes so the PDF includes the actual route comparison table
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
      a.download = 'connectroute_report.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('⚠️ Could not generate report — make sure the backend is running.')
    }
  }

  const alphaLabel = alpha >= 0.95 ? 'Fastest' : alpha <= 0.05 ? 'Most Connected' : `Balanced (${alpha.toFixed(2)})`

  return (
    <div
      className="absolute top-0 left-0 h-screen w-[360px] flex flex-col gap-3 p-4 overflow-y-auto z-30"
      style={{ background: 'rgba(10,10,20,0.92)', backdropFilter: 'blur(12px)', borderRight: '1px solid rgba(255,255,255,0.07)' }}
    >
      {/* Header */}
      <div>
        <div className="font-mono text-lg font-bold" style={{ color: '#3b82f6' }}>
          📡 ConnectRoute
        </div>
        <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
          Signal-aware routing · Chennai
        </div>
      </div>

      {/* FROM */}
      <SearchBox
        label="FROM"
        placeholder="Origin address..."
        onSelect={setOrigin}
        initialValue={origin?.name}
      />

      {/* TO */}
      <SearchBox
        label="TO"
        placeholder="Destination address..."
        onSelect={setDest}
        initialValue={dest?.name}
      />

      {/* Emergency preset */}
      <button
        onClick={onEmergency}
        className="w-full py-2 rounded-lg text-sm font-semibold transition-all btn-glow"
        style={{ border: '1px solid #ef4444', color: '#ef4444', background: 'transparent' }}
        onMouseEnter={e => e.target.style.background = '#ef444420'}
        onMouseLeave={e => e.target.style.background = 'transparent'}
      >
        🚑 Emergency Route
      </button>

      {/* Carrier Selection */}
      <div className="flex flex-col gap-1 mt-2">
        <label className="text-[10px] uppercase font-semibold" style={{ color: 'var(--text-muted)' }}>
          Mobile Network
        </label>
        <select
          value={carrier}
          onChange={(e) => setCarrier(e.target.value)}
          className="w-full p-2 outline-none text-sm rounded-lg"
          style={{ background: '#1c1c28', color: '#e2e8f0', border: '1px solid #334' }}
        >
          <option value="all">🌐 All Networks</option>
          <option value="airtel">Airtel</option>
          <option value="jio">Jio</option>
          <option value="vi">Vi (Vodafone Idea)</option>
          <option value="bsnl">BSNL</option>
        </select>
      </div>

      {/* Slider */}
      <div className="flex flex-col gap-2 mt-2">
        <div className="flex justify-between text-[10px]" style={{ color: 'var(--text-muted)' }}>
          <span>Speed</span>
          <span>Connectivity</span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={alpha}
          onChange={handleSlider}
        />
        <div className="text-center text-xs font-mono" style={{ color: '#3b82f6' }}>
          {alphaLabel}
        </div>
      </div>

      {/* Find Routes */}
      <button
        onClick={onFindRoutes}
        disabled={!origin || !dest || routesLoading}
        className="w-full py-3 rounded-lg font-semibold text-white transition-all btn-glow disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ background: '#3b82f6' }}
      >
        {routesLoading ? (
          <span className="flex items-center justify-center gap-2">
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Routing...
          </span>
        ) : 'Find Routes →'}
      </button>

      {/* Weather */}
      <div>
        <div className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-muted)' }}>Weather</div>
        {weatherLoading ? (
          <div className="w-4 h-4 border border-blue-500 border-t-transparent rounded-full animate-spin" />
        ) : (
          <WeatherCard weather={weather} />
        )}
      </div>

      {/* Signal Heatmap Toggle */}
      <button
        onClick={onToggleHeatmap}
        className="w-full py-2 rounded-lg text-sm transition-all"
        style={{
          border: `1px solid ${showHeatmap ? '#f97316' : 'rgba(255,255,255,0.15)'}`,
          color: showHeatmap ? '#f97316' : 'var(--text-muted)',
          background: showHeatmap ? 'rgba(249,115,22,0.08)' : 'transparent',
        }}
      >
        {showHeatmap ? '🟧 Hide Signal Heatmap' : '🟧 Show Signal Heatmap'}
      </button>

      {/* Download Report */}
      <button
        onClick={handleDownloadReport}
        className="w-full py-2 rounded-lg text-sm transition-all btn-glow"
        style={{ border: '1px solid rgba(255,255,255,0.15)', color: 'var(--text-muted)' }}
      >
        📄 Download Report
      </button>
    </div>
  )
}