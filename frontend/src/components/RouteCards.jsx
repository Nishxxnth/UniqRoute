export default function RouteCards({ routes, selectedIdx, onSelect }) {
  const getScoreStyle = (score) => {
    if (score >= 70) return { bg: 'rgba(34, 197, 94, 0.12)', color: '#22c55e', border: 'rgba(34, 197, 94, 0.25)' }
    if (score >= 40) return { bg: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', border: 'rgba(245, 158, 11, 0.25)' }
    return { bg: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', border: 'rgba(239, 68, 68, 0.25)' }
  }

  const getTrafficStyle = (ratio) => {
    if (ratio >= 0.75) return { label: 'Free Flow', color: '#22c55e', icon: '🟢' }
    if (ratio >= 0.50) return { label: 'Moderate', color: '#f59e0b', icon: '🟡' }
    if (ratio >= 0.30) return { label: 'Heavy', color: '#f97316', icon: '🟠' }
    return { label: 'Severe', color: '#ef4444', icon: '🔴' }
  }

  const LABELS = ['Fastest', 'Balanced', 'Most Connected']

  return (
    <div className="route-panel">
      <div className="route-cards-row">
        {routes.map((route, idx) => {
          const props = route.properties ?? route
          const scoreStyle = getScoreStyle(props.score ?? 50)
          const isSelected = selectedIdx === idx
          const color = props.color || '#3b82f6'

          const trafficRatio = props.avg_traffic_ratio ?? 0.85
          const trafficDelay = props.traffic_delay_min ?? 0
          const trafficStyle = getTrafficStyle(trafficRatio)
          const distanceKm = props.distance_km ?? 0

          return (
            <div
              key={idx}
              onClick={() => onSelect(isSelected ? null : idx)}
              className={`route-card ${isSelected ? 'selected' : ''}`}
              style={{
                opacity: selectedIdx !== null && selectedIdx !== idx ? 0.45 : 1,
                '--card-color': color,
              }}
            >
              {/* Left color bar */}
              <div style={{
                position: 'absolute', top: 0, left: 0, bottom: 0, width: '3px',
                background: color, borderRadius: '3px 0 0 3px',
              }} />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <span className="route-name" style={{ color }}>
                  {LABELS[idx] || props.name}
                </span>
                <span className="route-score" style={{
                  background: scoreStyle.bg,
                  color: scoreStyle.color,
                  border: `1px solid ${scoreStyle.border}`,
                }}>
                  {props.score}
                </span>
              </div>

              <div className="route-eta">
                {props.eta_min}<span>min</span>
                {distanceKm > 0 && (
                  <span style={{ fontSize: '11px', color: '#9ca3af', marginLeft: '8px' }}>
                    {distanceKm} km
                  </span>
                )}
              </div>

              {/* Traffic info row */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                marginTop: '6px', marginBottom: '4px',
                padding: '4px 8px',
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '6px',
                fontSize: '11px',
              }}>
                <span>{trafficStyle.icon}</span>
                <span style={{ color: trafficStyle.color, fontWeight: 600 }}>
                  {trafficStyle.label}
                </span>
                {trafficDelay > 0 && (
                  <span style={{ color: '#f97316', marginLeft: 'auto' }}>
                    +{trafficDelay} min delay
                  </span>
                )}
                {trafficDelay === 0 && (
                  <span style={{ color: '#6b7280', marginLeft: 'auto' }}>
                    No delay
                  </span>
                )}
              </div>

              <div className="route-meta" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {(props.dead_zones || 0) > 0 ? (
                    <span className="dead-zone-tag" style={{ color: '#ef4444' }}>
                      ⚠ {props.dead_zone_segments?.length || 1} dead zone block{props.dead_zone_segments?.length > 1 ? 's' : ''} ({props.dead_zones} edges)
                    </span>
                  ) : (
                    <span className="dead-zone-tag" style={{ color: '#22c55e' }}>
                      ✓ No dead zones
                    </span>
                  )}
                  <span className="dead-zone-tag">
                    📶 Score: {props.score}/100
                  </span>
                </div>
                {props.dead_zone_segments?.length > 0 && (
                  <div style={{ fontSize: '9px', color: '#93c5fd', background: 'rgba(59, 130, 246, 0.1)', padding: '2px 6px', borderRadius: '4px', width: 'fit-content' }}>
                    ℹ️ Nav data will pre-cache {props.dead_zone_segments[0].start_dist_m > 0 ? `at ${props.dead_zone_segments[0].start_dist_m}m` : 'immediately'}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}