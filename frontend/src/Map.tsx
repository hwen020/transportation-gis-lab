import type { Feature, Location, Position } from './types'

export const colors: Record<string, string> = {
  Interstate: '#64d8ff', 'Principal arterial': '#85e1ac', 'Minor arterial': '#f2c46b', Collector: '#f3a4b6',
}

const parts = (feature: Feature) => feature.geometry.type === 'LineString'
  ? [feature.geometry.coordinates] : feature.geometry.coordinates

export function RoadMap({ features, baseline, selected, choose, marker }: {
  features: Feature[]; baseline: Feature[]; selected: string; choose: (id: string) => void; marker: Location | null
}) {
  const all = baseline.flatMap(feature => parts(feature).flat())
  if (!all.length) return <p>No road geometries available.</p>
  const west = Math.min(...all.map(([x]) => x))
  const east = Math.max(...all.map(([x]) => x))
  const south = Math.min(...all.map(([, y]) => y))
  const north = Math.max(...all.map(([, y]) => y))
  const cosLat = Math.cos((south + north) / 2 * Math.PI / 180)
  const scale = Math.min(630 / Math.max((east - west) * cosLat, 1e-6), 325 / Math.max(north - south, 1e-6))
  const xy = ([lon, lat]: Position) => [
    360 + (lon - (west + east) / 2) * cosLat * scale,
    200 - (lat - (north + south) / 2) * scale,
  ]
  const point = marker && xy([marker.lon, marker.lat])
  return <>
    <svg className="map" viewBox="0 0 720 400" aria-label="Selectable synthetic roadway network">
      <defs><pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">
        <path d="M36 0H0V36" fill="none" stroke="#254152" />
      </pattern></defs>
      <rect width="720" height="400" fill="url(#grid)" />
      <text x="674" y="34" fill="#bcd1d9">N ↑</text>
      {features.map(feature => {
        const p = feature.properties
        const lines = parts(feature).map(line => line.map((coord, index) => (index ? 'L' : 'M') + xy(coord).join(' ')).join(' ')).join(' ')
        return <path key={feature.id} d={lines} role="button" tabIndex={0}
          aria-label={'Map segment ' + feature.id} aria-pressed={feature.id === selected}
          className={'road ' + (feature.id === selected ? 'selected' : '')}
          stroke={colors[p.functional_class] || '#aab4bd'} onClick={() => choose(feature.id)}
          onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(feature.id) } }}>
          <title>{feature.id} · {p.route_id} · {p.from_measure_mi}–{p.to_measure_mi} mi · {p.functional_class}</title>
        </path>
      })}
      {point && <circle cx={point[0]} cy={point[1]} r="7" fill="white" stroke="#092436" strokeWidth="2" pointerEvents="none" />}
    </svg>
    <ul className="legend">{Object.entries(colors).map(([name, color]) =>
      <li key={name}><span style={{ background: color }} />{name}</li>)}</ul>
  </>
}
