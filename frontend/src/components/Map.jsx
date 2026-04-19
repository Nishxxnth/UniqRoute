import { useEffect, useRef, useCallback, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const HEATMAP_SOURCE = 'heatmap-source'
const TOWERS_SOURCE = 'towers-source'
const ROUTE_SOURCES = ['route-fast-source', 'route-blended-source', 'route-connected-source']
const ROUTE_COLORS = ['#e74c3c', '#3b82f6', '#22c55e']  // Red, Blue (balanced), Green

export default function Map({ heatmapData, towersData, routes, selectedRouteIdx, onRouteSelect, showHeatmap = false, showTowers = false, carPositionRef, isEmergency = false, isImmersive = false, isPaused = false }) {
  const mapRef = useRef(null)
  const containerRef = useRef(null)
  const popupRef = useRef(null)
  const overlapPopupsRef = useRef([])
  const startMarkerRef = useRef(null)
  const endMarkerRef = useRef(null)
  const carMarkerRef = useRef(null)
  const animFrameRef = useRef(null)
  
  const [mapLoaded, setMapLoaded] = useState(false)
  
  const isPausedRef = useRef(isPaused)
  useEffect(() => {
    isPausedRef.current = isPaused
  }, [isPaused])

  const isImmersiveRef = useRef(isImmersive)
  useEffect(() => {
    isImmersiveRef.current = isImmersive
  }, [isImmersive])

  const initSources = useCallback(() => {
    if (!mapRef.current) return
    const map = mapRef.current

    map.addSource(HEATMAP_SOURCE, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })

    map.addSource(TOWERS_SOURCE, {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
      cluster: true,
      clusterMaxZoom: 13,
      clusterRadius: 40,
      buffer: 128,
      tolerance: 0.375
    })

    ROUTE_SOURCES.forEach(src => {
      map.addSource(src, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
    })
  }, [])

  const initLayers = useCallback(() => {
    if (!mapRef.current) return
    const map = mapRef.current

    // Heatmap layer — color scale designed for dark maps
    map.addLayer({
      id: 'heatmap-layer',
      type: 'line',
      source: HEATMAP_SOURCE,
      minzoom: 0,
      maxzoom: 22,
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
        visibility: 'none'
      },
      paint: {
        'line-color': [
          'interpolate', ['linear'], ['get', 'connectivity_score'],
          0,  '#1a0000',    // score 0:   near-black red (dead zone — almost invisible)
          15, '#7f1d1d',    // score 15:  dark red (very poor)
          30, '#dc2626',    // score 30:  red (poor — dead zone threshold)
          45, '#f97316',    // score 45:  orange (below average)
          60, '#eab308',    // score 60:  yellow (moderate)
          75, '#22c55e',    // score 75:  green (good)
          90, '#06b6d4',    // score 90:  cyan (very good — bright and glowing)
          100, '#ffffff',   // score 100: white (excellent — maximum brightness)
        ],
        'line-width': [
          'interpolate', ['linear'], ['get', 'connectivity_score'],
          0, 1.5,    // thin lines for dead zones (less visual noise)
          50, 2.5,
          100, 3.5,  // thicker lines for strong signal (more visible)
        ],
        'line-opacity': [
          'interpolate', ['linear'], ['get', 'connectivity_score'],
          0, 0.3,    // dim for dead zones
          50, 0.6,
          100, 0.85, // bright for strong signal
        ],
      },
    })

    // Add towers layer (Clustered)
    map.addLayer({
      id: 'heatmap-towers-clusters',
      type: 'circle',
      source: TOWERS_SOURCE,
      filter: ['has', 'point_count'],
      layout: {
        visibility: 'none'
      },
      paint: {
        'circle-color': [
          'step',
          ['get', 'point_count'],
          '#3b82f6', // blue for small clusters
          100, '#f59e0b', // yellow for medium clusters
          750, '#ef4444' // red for large clusters
        ],
        'circle-radius': [
          'step',
          ['get', 'point_count'],
          15,
          100, 20,
          750, 30
        ],
        'circle-opacity': 0.85,
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff'
      }
    })

    // Cluster count labels
    map.addLayer({
      id: 'heatmap-towers-cluster-count',
      type: 'symbol',
      source: TOWERS_SOURCE,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': ['Noto Sans Regular'],
        'text-size': 11,
        'text-allow-overlap': true,
        visibility: 'none'
      },
      paint: {
        'text-color': '#ffffff',
        'text-halo-color': '#000000',
        'text-halo-width': 1
      }
    })

    // Unclustered towers
    map.addLayer({
      id: 'heatmap-towers',
      type: 'circle',
      source: TOWERS_SOURCE,
      filter: ['!', ['has', 'point_count']],
      layout: {
        visibility: 'none'
      },
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          9, 2,
          13, 4,
          16, 7
        ],
        'circle-color': [
          'match',
          ['get', 'radio'],
          'NR', '#22c55e',
          'LTE', '#3b82f6',
          'UMTS', '#f59e0b',
          '#ef4444'
        ],
        'circle-stroke-width': 1,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.9
      }
    })

    // Route layers
    ROUTE_SOURCES.forEach((src, idx) => {
      const color = ROUTE_COLORS[idx]
      map.addLayer({
        id: `${src}-glow`,
        type: 'line',
        source: src,
        paint: {
          'line-color': color,
          'line-width': 12,
          'line-opacity': 0.2,
          'line-blur': 8,
        },
      })
      map.addLayer({
        id: `${src}-line`,
        type: 'line',
        source: src,
        paint: {
          'line-color': color,
          'line-width': 5,
          'line-opacity': 0.9,
        },
      })
    })

    // Click on heatmap roads
    map.on('click', 'heatmap-layer', (e) => {
      if (popupRef.current) popupRef.current.remove()
      const props = e.features[0].properties

      const popup = new maplibregl.Popup({ closeButton: false, className: 'score-popup' })
        .setLngLat(e.lngLat)
        .setDOMContent(createPopupContent(props))
        .addTo(map)
      popupRef.current = popup
    })

    map.on('mouseenter', 'heatmap-layer', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'heatmap-layer', () => {
      map.getCanvas().style.cursor = ''
    })

    // Click on towers
    map.on('click', 'heatmap-towers', (e) => {
      if (popupRef.current) popupRef.current.remove()
      const props = e.features[0].properties
      const container = document.createElement('div')
      container.innerHTML = `
        <div style="background:rgba(20,20,30,0.95);padding:10px;border-radius:6px;font-family:Inter,sans-serif;color:white;">
          <h4 style="margin:0 0 5px 0;">📡 Cell Tower</h4>
          <div style="font-size:11px;">Carrier: <strong style="color:#e2e8f0;">${props.carrier.toUpperCase()}</strong></div>
          <div style="font-size:11px;">Tech: <strong style="color:#3b82f6;">${props.radio}</strong></div>
          <div style="font-size:11px;">Strength: <strong>${Math.round(props.averageSignal)} dBm</strong></div>
        </div>
      `
      popupRef.current = new maplibregl.Popup({ closeButton: false })
        .setLngLat(e.lngLat)
        .setDOMContent(container)
        .addTo(map)
    })
    map.on('mouseenter', 'heatmap-towers', () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'heatmap-towers', () => {
      map.getCanvas().style.cursor = ''
    })
  }, [])

  const createPopupContent = (props) => {
    const container = document.createElement('div')
    container.innerHTML = `
      <div style="background:rgba(10,10,20,0.95);padding:12px;border-radius:8px;width:240px;font-family:Inter,sans-serif">
        <div style="font-family:JetBrains Mono,monospace;font-size:14px;font-weight:700;color:#f1f5f9;margin-bottom:8px">
          Signal Score: ${props.connectivity_score}/100
        </div>
        ${['rssi','distance','network','weather','obstacles','congestion'].map(f => {
          const label = f.charAt(0).toUpperCase() + f.slice(1)
          const val = props[`score_${f}`] || props.connectivity_score || 50
          return `
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
            <span style="font-size:10px;color:#6b7280;width:70px">${label}</span>
            <div style="flex:1;height:4px;border-radius:2px;background:rgba(255,255,255,0.1)">
              <div style="width:${val}%;height:100%;border-radius:2px;background:${scoreColor(val)}"></div>
            </div>
            <span style="font-size:10px;font-family:JetBrains Mono,monospace;color:#f1f5f9">${val}</span>
          </div>`
        }).join('')}
      </div>
    `
    return container
  }

  const scoreColor = (v) => {
    if (v >= 70) return '#22c55e'
    if (v >= 40) return '#f97316'
    return '#ef4444'
  }

  useEffect(() => {
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [80.27, 13.08],
      zoom: 12,
      pitch: 45,
      bearing: -10,
    })

    mapRef.current.on('load', () => {
      initSources()
      initLayers()
      setMapLoaded(true)
    })

    // Resize map when container changes size
    const observer = new ResizeObserver(() => {
      if (mapRef.current) mapRef.current.resize()
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      if (mapRef.current) mapRef.current.remove()
    }
  }, [initSources, initLayers])

  // Update heatmap data — runs once map is ready AND whenever data changes
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !heatmapData) return
    const src = mapRef.current.getSource(HEATMAP_SOURCE)
    if (!src) return
    try { src.setData(heatmapData) } catch(e) { console.warn('heatmap setData err', e) }
  }, [heatmapData, mapLoaded])

  // Update towers data
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !towersData) return
    const src = mapRef.current.getSource(TOWERS_SOURCE)
    if (!src) return
    try { src.setData(towersData) } catch(e) { console.warn('towers setData err', e) }
  }, [towersData, mapLoaded])

  // Toggle heatmap layer visibility
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return
    const visibility = showHeatmap ? 'visible' : 'none'
    
    if (mapRef.current.getLayer('heatmap-layer')) {
      mapRef.current.setLayoutProperty('heatmap-layer', 'visibility', visibility)
    }
  }, [showHeatmap, mapLoaded])

  // Toggle towers layer visibility
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return
    const visibility = showTowers ? 'visible' : 'none'
    
    if (mapRef.current.getLayer('heatmap-towers')) {
      mapRef.current.setLayoutProperty('heatmap-towers', 'visibility', visibility)
    }
    if (mapRef.current.getLayer('heatmap-towers-clusters')) {
      mapRef.current.setLayoutProperty('heatmap-towers-clusters', 'visibility', visibility)
    }
    if (mapRef.current.getLayer('heatmap-towers-cluster-count')) {
      mapRef.current.setLayoutProperty('heatmap-towers-cluster-count', 'visibility', visibility)
    }
  }, [showTowers, mapLoaded])

  // Update routes
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || routes.length === 0) return

    ROUTE_SOURCES.forEach((src, idx) => {
      const source = mapRef.current.getSource(src)
      if (!source) return
      const data = routes[idx] && routes[idx].geometry
        ? { type: 'Feature', geometry: routes[idx].geometry, properties: {} }
        : { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} }
      source.setData(data)
    })

    // Fit bounds
    const allCoords = routes.flatMap(r => r.geometry.coordinates)
    if (allCoords.length === 0) return
    const lons = allCoords.map(c => c[0])
    const lats = allCoords.map(c => c[1])
    mapRef.current.fitBounds(
      [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: { top: 40, bottom: 40, left: 40, right: 40 } }
    )

    // Compute Shared Overlaps for Cloud Tooltips
    overlapPopupsRef.current.forEach(p => p.remove())
    overlapPopupsRef.current = []

    if (routes.length >= 2) {
      const c1 = routes[0].geometry.coordinates.map(c => c.join(','))
      const c2 = routes[1].geometry.coordinates.map(c => c.join(','))
      const c3 = routes.length > 2 ? routes[2].geometry.coordinates.map(c => c.join(',')) : []

      const findMid = (arrA, arrB, nameA, nameB) => {
        const shared = arrA.filter(c => arrB.includes(c))
        if (shared.length > 20) {
          const midPointStr = shared[Math.floor(shared.length / 2)]
          return { pt: midPointStr.split(',').map(Number), label: `${nameA} + ${nameB}` }
        }
        return null
      }

      const p1 = findMid(c1, c2, 'Fastest', 'Balanced')
      const p2 = findMid(c2, c3, 'Balanced', 'Connected')
      const p3 = findMid(c1, c3, 'Fastest', 'Connected')

      const validPopups = [p1, p2, p3].filter(Boolean)

      validPopups.forEach(ov => {
        const el = document.createElement('div')
        el.innerHTML = `☁️ Shared: ${ov.label}`
        el.style.cssText = 'background:rgba(255,255,255,0.9);color:#1e293b;padding:4px 8px;border-radius:12px;font-size:10px;font-weight:bold;border:1px solid rgba(0,0,0,0.1);box-shadow:0 4px 6px rgba(0,0,0,0.1);pointer-events:none;'

        const pop = new maplibregl.Marker({ element: el })
          .setLngLat(ov.pt)
          .addTo(mapRef.current)
        overlapPopupsRef.current.push(pop)
      })
    }

    // ── Origin & Destination Markers ─────────────────────────────
    // Clean up old markers
    if (startMarkerRef.current) { startMarkerRef.current.remove(); startMarkerRef.current = null }
    if (endMarkerRef.current) { endMarkerRef.current.remove(); endMarkerRef.current = null }

    // Get first and last coordinate from the first route
    const firstRoute = routes[0]?.geometry?.coordinates
    if (firstRoute && firstRoute.length >= 2) {
      const startCoord = firstRoute[0]           // [lon, lat]
      const endCoord = firstRoute[firstRoute.length - 1]  // [lon, lat]

      // Origin marker: white pulsing dot
      const startEl = document.createElement('div')
      startEl.innerHTML = `
        <div style="position:relative;width:22px;height:22px;">
          <div style="position:absolute;inset:0;border-radius:50%;background:rgba(255,255,255,0.2);animation:pulse-ring 1.5s ease-out infinite;"></div>
          <div style="position:absolute;top:4px;left:4px;width:14px;height:14px;border-radius:50%;background:white;border:3px solid #3b82f6;box-shadow:0 0 8px rgba(59,130,246,0.6);"></div>
        </div>
      `
      startMarkerRef.current = new maplibregl.Marker({ element: startEl, anchor: 'center' })
        .setLngLat(startCoord)
        .addTo(mapRef.current)

      // Destination marker: red Google Maps-style pin
      const endEl = document.createElement('div')
      endEl.innerHTML = `
        <div style="position:relative;width:30px;height:42px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5));">
          <svg viewBox="0 0 30 42" width="30" height="42" xmlns="http://www.w3.org/2000/svg">
            <path d="M15 0C6.7 0 0 6.7 0 15c0 10.5 15 27 15 27s15-16.5 15-27C30 6.7 23.3 0 15 0z" fill="#ef4444"/>
            <circle cx="15" cy="14" r="6" fill="white"/>
          </svg>
        </div>
      `
      endMarkerRef.current = new maplibregl.Marker({ element: endEl, anchor: 'bottom' })
        .setLngLat(endCoord)
        .addTo(mapRef.current)
    }
  }, [routes, mapLoaded])

  // Fade non-selected routes
  useEffect(() => {
    if (!mapRef.current || !mapRef.current.isStyleLoaded()) return
    ROUTE_SOURCES.forEach((src, idx) => {
      const layerId = `${src}-line`
      const glowId = `${src}-glow`
      if (mapRef.current.getLayer(layerId)) {
        const isSelected = selectedRouteIdx === null || selectedRouteIdx === idx
        mapRef.current.setPaintProperty(layerId, 'line-opacity', isSelected ? 0.9 : 0.15)
        mapRef.current.setPaintProperty(glowId, 'line-opacity', isSelected ? 0.2 : 0.0)
        if (selectedRouteIdx === idx) {
          mapRef.current.moveLayer(glowId)
          mapRef.current.moveLayer(layerId)
        }
      }
    })
  }, [selectedRouteIdx])

  // Handle exiting immersive mode
  useEffect(() => {
    if (mapRef.current && !isImmersive) {
      mapRef.current.easeTo({ pitch: 0, bearing: 0, zoom: 12.5 })
    }
  }, [isImmersive])

  // ── Car Simulation & Dead Zone Advisory ────────────────
  useEffect(() => {
    if (!mapRef.current || !routes || routes.length === 0) return

    // Clean up previous interval/animation
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    if (carMarkerRef.current) {
        carMarkerRef.current.remove()
        carMarkerRef.current = null
    }

    // Pick active route
    const activeIdx = selectedRouteIdx !== null ? selectedRouteIdx : 0
    const activeRoute = routes[activeIdx]
    const coords = activeRoute?.geometry?.coordinates
    const deadZoneSegments = activeRoute?.properties?.dead_zone_segments || []

    if (!coords || coords.length < 2) return

    const carIcon = isEmergency ? '🚑' : '🚗'

    // Car marker: representing the moving vehicle
    const carEl = document.createElement('div')
    carEl.innerHTML = `
      <div style="font-size:24px; filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5)); transition: transform 0.1s;">
        ${carIcon}
      </div>
    `
    // Mini-popup attached to the car
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 15 })
    const popupBubble = (content) => `<div style="background: rgba(255,255,255,0.95); padding: 4px 8px; border-radius: 8px; border: 1px solid rgba(0,0,0,0.1); box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;">${content}</div>`
    popup.setHTML(popupBubble('<div style="font-size:10px; font-weight:bold; color:#1e293b;">Online</div>'))
    
    carMarkerRef.current = new maplibregl.Marker({ element: carEl, anchor: 'center' })
      .setLngLat(coords[0])
      .setPopup(popup)
      .addTo(mapRef.current)
    
    // Auto open popup
    carMarkerRef.current.togglePopup()

    let startTime = null
    const duration = 15000 // 15 seconds to travel full route
    const totalDist = activeRoute.properties.distance_km * 1000
    
    let isFollowing = true
    const breakFollow = () => { isFollowing = false }
    mapRef.current.on('dragstart', breakFollow)
    mapRef.current.on('wheel', breakFollow)
    let lastTime = null

    const animateCar = (timestamp) => {
      if (!startTime) startTime = timestamp
      if (!lastTime) lastTime = timestamp

      if (isPausedRef.current) {
         startTime += (timestamp - lastTime)
         lastTime = timestamp
         animFrameRef.current = requestAnimationFrame(animateCar)
         return
      }

      const progress = Math.min((timestamp - startTime) / duration, 1)
      lastTime = timestamp

      // Calculate path distance ratio using coordinate interpolation
      const pointIndexExact = progress * (coords.length - 1)
      const index = Math.floor(pointIndexExact)
      const remainder = pointIndexExact - index

      if (index < coords.length - 1) {
        const p1 = coords[index]
        const p2 = coords[index + 1]
        const lng = p1[0] + (p2[0] - p1[0]) * remainder
        const lat = p1[1] + (p2[1] - p1[1]) * remainder
        
        carMarkerRef.current.setLngLat([lng, lat])
        if (carPositionRef) carPositionRef.current = [lng, lat]

        // Smoothed rotation — only update if angle changed by >8 degrees to prevent jitter
        const rawAngle = Math.atan2(p2[1]-p1[1], p2[0]-p1[0]) * (180/Math.PI)
        const displayAngle = rawAngle > -90 && rawAngle < 90 ? rawAngle : rawAngle + 180
        const prevAngle = parseFloat(carEl.firstElementChild.dataset.angle || 0)
        if (Math.abs(displayAngle - prevAngle) > 8) {
          carEl.firstElementChild.style.transform = `rotate(${displayAngle}deg)`
          carEl.firstElementChild.dataset.angle = displayAngle
        }

        if (isImmersiveRef.current && isFollowing) {
            mapRef.current.jumpTo({
                center: [lng, lat],
                zoom: 17,
                pitch: 65,
                bearing: 90 - rawAngle
            })
        }

        // Dead zone check (500m before)
        const currentDistM = progress * totalDist
        let alertActive = false
        for (const dz of deadZoneSegments) {
            const distToDz = dz.start_dist_m - currentDistM
            if (distToDz > 0 && distToDz <= 500) {
               popup.setHTML(popupBubble(`<div style="font-size:10px; font-weight:bold; color:#f97316;">⚠️ Dead Zone in ${Math.round(distToDz)}m<br/>⬇️ Pre-caching GPS</div>`))
               alertActive = true
               break
            } else if (distToDz <= 0 && currentDistM <= dz.start_dist_m + dz.length_m) {
               popup.setHTML(popupBubble(`<div style="font-size:10px; font-weight:bold; color:#ef4444;">❌ Dead Zone<br/>SMS Fallback</div>`))
               alertActive = true
               break
             }
        }

        if (!alertActive) {
            popup.setHTML(popupBubble('<div style="font-size:10px; font-weight:bold; color:#22c55e;">📶 Online</div>'))
        }

        animFrameRef.current = requestAnimationFrame(animateCar)
      }
    }

    animFrameRef.current = requestAnimationFrame(animateCar)

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      if (carMarkerRef.current) { carMarkerRef.current.remove(); carMarkerRef.current = null }
      if (mapRef.current) {
        mapRef.current.off('dragstart', breakFollow)
        mapRef.current.off('wheel', breakFollow)
      }
    }
  }, [routes, selectedRouteIdx])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}