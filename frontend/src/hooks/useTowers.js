import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export function useTowers(carrier = 'all', enabled = false) {
  const [towersData, setTowersData] = useState({ type: 'FeatureCollection', features: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Track which carriers we have already fetched so we only download once per carrier
  const fetchedRef = useRef(new Set())

  useEffect(() => {
    if (!enabled) return
    const key = carrier
    if (fetchedRef.current.has(key)) return  // already in memory — skip re-download
    setLoading(true)
    axios.get(`/api/towers?carrier=${carrier}`)
      .then(res => {
        setTowersData(res.data)
        fetchedRef.current.add(key)
        setError(null)
      })
      .catch(err => {
        console.error('Towers fetch failed:', err)
        setError('Towers unavailable')
      })
      .finally(() => setLoading(false))
  }, [carrier, enabled])

  return { towersData, loading, error }
}
