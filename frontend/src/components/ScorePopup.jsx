export default function ScorePopup({ score, factors }) {
  const scoreColor = (v) => {
    if (v >= 70) return '#22c55e'
    if (v >= 40) return '#f97316'
    return '#ef4444'
  }

  const factorLabels = {
    rssi: 'Signal (RSSI)',
    distance: 'Distance',
    network: 'Network Type',
    weather: 'Weather',
    obstacles: 'Obstacles',
    congestion: 'Congestion',
  }

  return (
    <div
      className="rounded-xl p-4 w-60"
      style={{ background: 'rgba(10,10,20,0.95)', fontFamily: 'Inter, sans-serif' }}
    >
      <div className="font-mono text-base font-bold mb-3" style={{ color: '#f1f5f9' }}>
        Signal Score: {score}/100
      </div>
      <div className="flex flex-col gap-2">
        {Object.entries(factorLabels).map(([key, label]) => {
          const val = factors?.[key] ?? score
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="text-[10px] w-20 flex-shrink-0" style={{ color: 'var(--text-muted)' }}>
                {label}
              </span>
              <div
                className="h-1 flex-1 rounded"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              >
                <div
                  className="h-full rounded"
                  style={{ width: `${val}%`, background: scoreColor(val) }}
                />
              </div>
              <span className="text-[10px] font-mono w-8 text-right" style={{ color: '#f1f5f9' }}>
                {Math.round(val)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}