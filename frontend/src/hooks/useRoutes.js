import { useState, useCallback } from 'react'
import axios from 'axios'

export function useRoutes() {
  const [routes, setRoutes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchRoutes = useCallback(async (origin, dest, alpha, carrier = 'all', emergency = false) => {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.post('/api/routes', {
        origin_lat: origin.lat,
        origin_lon: origin.lon,
        dest_lat: dest.lat,
        dest_lon: dest.lon,
        alpha,
        carrier,
        emergency,
      })
      setRoutes(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to compute routes')
    } finally {
      setLoading(false)
    }
  }, [])

  return { routes, loading, error, fetchRoutes }
}