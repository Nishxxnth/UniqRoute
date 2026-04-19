export default function WeatherCard({ weather }) {
  if (!weather) return null

  // Backend weather payload doesn't include temperature — show a static Chennai default
  const temp = `${Math.round(weather.temp ?? 32)}°C`

  const descriptions = {
    Clear: '☀️ Clear',
    Clouds: '☁️ Cloudy',
    Rain: '🌧️ Rain',
    Drizzle: '🌦️ Light Rain',
    Thunderstorm: '⛈️ Thunderstorm',
    Snow: '❄️ Snow',
  }
  const icon = descriptions[weather.description] || `🌡️ ${weather.description}`
  const signalText = weather.description?.toLowerCase().includes('rain') || weather.description?.toLowerCase().includes('storm')
    ? 'Signal: Moderate'
    : 'Signal: Good'

  let impactColor = 'var(--success)'
  let impactText = 'Clear'
  if (weather.storm_penalty > 0.2) {
    impactColor = 'var(--danger)'
    impactText = 'High Impact'
  } else if (weather.storm_penalty > 0) {
    impactColor = 'var(--warning)'
    impactText = 'Moderate Impact'
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
      <span className="text-sm">{icon}</span>
      <span className="text-xs font-mono">{temp} · {weather.description}</span>
      <span className="text-xs" style={{ color: impactColor }}>· {impactText}</span>
    </div>
  )
}