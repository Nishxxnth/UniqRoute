import { useState, useRef } from 'react'

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
const CHENNAI_VIEWBOX = '80.1,12.8,80.35,13.2'

export default function SearchBox({ label, placeholder, onSelect, initialValue }) {
  const [query, setQuery] = useState(initialValue || '')
  const [results, setResults] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceTimer = useRef(null)
  const lastCallRef = useRef(0)

  const searchNominatim = async (q) => {
    if (!q.trim()) {
      setResults([])
      return
    }
    const now = Date.now()
    if (now - lastCallRef.current < 1000) return
    lastCallRef.current = now

    setLoading(true)
    try {
      const params = new URLSearchParams({
        q: q + ' Chennai',
        countrycodes: 'in',
        viewbox: CHENNAI_VIEWBOX,
        bounded: '1',
        format: 'json',
        addressdetails: '1',
        limit: '5',
      })
      const res = await fetch(`${NOMINATIM_URL}?${params}`, {
        headers: { 'User-Agent': 'ConnectRoute/1.0' },
      })
      const data = await res.json()
      setResults(data)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleInput = (e) => {
    const val = e.target.value
    setQuery(val)
    clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => searchNominatim(val), 500)
  }

  const handleSelect = (result) => {
    const name = result.display_name.length > 45
      ? result.display_name.substring(0, 45) + '…'
      : result.display_name
    setQuery(name)
    setShowDropdown(false)
    onSelect({
      lat: parseFloat(result.lat),
      lon: parseFloat(result.lon),
      name: result.display_name,
    })
  }

  const truncate = (str, len) =>
    str.length > len ? str.substring(0, len) + '…' : str

  return (
    <div className="search-input-wrap">
      <label>{label}</label>
      <input
        type="text"
        value={query}
        onChange={handleInput}
        onFocus={() => setShowDropdown(true)}
        onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
        placeholder={placeholder}
      />
      {loading && (
        <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)' }}>
          <div className="spinner" style={{ width: '12px', height: '12px', borderWidth: '1.5px' }} />
        </div>
      )}
      {showDropdown && results.length > 0 && (
        <div className="search-dropdown">
          {results.map((r, i) => (
            <div
              key={i}
              onMouseDown={() => handleSelect(r)}
              className="search-dropdown-item"
            >
              <span style={{
                fontSize: '9px', padding: '1px 5px', borderRadius: '4px',
                background: 'rgba(59,130,246,0.15)', color: '#93c5fd', marginRight: '6px',
              }}>
                {r.type || r.class}
              </span>
              {truncate(r.display_name, 55)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}