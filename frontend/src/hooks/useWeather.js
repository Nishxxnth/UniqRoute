import { useState, useEffect } from 'react'
import axios from 'axios'

export function useWeather() {
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get('/api/weather')
      .then(res => setWeather(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return { weather, loading }
}