import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export function useHeatmap(carrier = 'all', enabled = false) {
  const [heatmapData, setHeatmapData] = useState({ type: 'FeatureCollection', features: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  // Track which carriers we have already fetched so we only download once per carrier
  const fetchedRef = useRef(new Set())

  useEffect(() => {
    if (!enabled) return
    const key = carrier
    if (fetchedRef.current.has(key)) return  // already in memory — skip re-download
    setLoading(true)
    axios.get(`/api/heatmap?carrier=${carrier}`)
      .then(res => {
        setHeatmapData(res.data)
        fetchedRef.current.add(key)
        setError(null)
      })
      .catch(err => {
        console.error('Heatmap fetch failed:', err)
        setError('Heatmap unavailable')
      })
      .finally(() => setLoading(false))
  }, [carrier, enabled])

  return { heatmapData, loading, error }
}