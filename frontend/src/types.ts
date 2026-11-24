export type Position = [number, number]
export type Geometry = { type: 'LineString'; coordinates: Position[] }
  | { type: 'MultiLineString'; coordinates: Position[][] }
export type Edit = {
  segment_id: string
  from_measure_mi: number
  to_measure_mi: number
  functional_class: string
  lanes: number
  surface: string
  aadt: number
}
export type Segment = Omit<Edit, 'surface'> & { route_id: string; surface: string | null }
export type Feature = { id: string; geometry: Geometry; properties: Segment }
export type Metadata = Record<string, string | number>
export type Finding = { id: string; rule_code: string; severity: string; segment_ids: string[]; details: string }
export type Bundle = {
  segments: { type: 'FeatureCollection'; features: Feature[]; metadata: Metadata }
  qa: Finding[]
  summary: {
    title: string; segment_count: number; segment_miles: number; completeness_pct: number | null
    limitations: string; groups: Record<string, { group: string; segments: number; segment_miles: number }[]>
  }
  audit: { id: number; segment_id: string; timestamp: string; before: Segment; after: Segment }[]
  csv: string
}
export type Location = { milepoint: number; lon: number; lat: number; along_geometry_m: number; route_geometry_m: number; offset_m?: number }

export async function post<T>(path: string, data: unknown): Promise<T> {
  const response = await fetch('/api/v1/' + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  })
  const result = await response.json()
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Check the input fields and try again.')
  return result
}

export function download(name: string, mime: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type: mime }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
