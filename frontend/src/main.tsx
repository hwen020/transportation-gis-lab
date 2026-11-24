import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import { colors, RoadMap } from './Map'
import { download, post } from './types'
import type { Bundle, Edit, Location, Segment } from './types'
import './style.css'

const message = (error: unknown) => error instanceof Error ? error.message : String(error)
const classes = Object.keys(colors)
const surfaces = ['Asphalt', 'Concrete', 'Gravel']
const groupLabels: Record<string, string> = {
  route_id: 'Route', functional_class: 'Functional class', traffic_band: 'Traffic band', mile_band: 'Segment-mile band',
}

function Editor({ segment, save, busy }: { segment: Segment; save: (edit: Edit) => void; busy: boolean }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    save({
      segment_id: segment.segment_id, from_measure_mi: Number(fields.get('from')),
      to_measure_mi: Number(fields.get('to')), lanes: Number(fields.get('lanes')),
      aadt: Number(fields.get('aadt')), functional_class: String(fields.get('class')), surface: String(fields.get('surface')),
    })
  }
  return <form className="form-grid" onSubmit={submit}>
    <p className="wide selection">{segment.segment_id} / {segment.route_id}</p>
    <label>From milepoint<input required type="number" name="from" min="0" step="any" defaultValue={segment.from_measure_mi} /></label>
    <label>To milepoint<input required type="number" name="to" min="0" step="any" defaultValue={segment.to_measure_mi} /></label>
    <label className="wide">Functional class<select name="class" defaultValue={segment.functional_class}>{classes.map(value => <option key={value}>{value}</option>)}</select></label>
    <label>Lanes<input required name="lanes" type="number" min="1" max="12" defaultValue={segment.lanes} /></label>
    <label>AADT<input required name="aadt" type="number" min="0" defaultValue={segment.aadt} /></label>
    <label className="wide">Surface<select required name="surface" defaultValue={segment.surface ?? ''}><option value="">Missing</option>{surfaces.map(value => <option key={value}>{value}</option>)}</select></label>
    <button className="primary wide" disabled={busy}>Save inventory attributes</button>
  </form>
}

function LrsTool({ routes, setMarker }: { routes: string[]; setMarker: (value: Location | null) => void }) {
  const [mode, setMode] = useState('locate')
  const [result, setResult] = useState<Location | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const route_id = String(data.get('route'))
    const query = mode === 'locate' ? { route_id, milepoint: Number(data.get('milepoint')) }
      : { route_id, lon: Number(data.get('lon')), lat: Number(data.get('lat')) }
    setBusy(true)
    setError('')
    try {
      const answer = await post<Location>('lrs/' + mode, query)
      setResult(answer)
      setMarker(answer)
    } catch (error) {
      setResult(null)
      setMarker(null)
      setError(message(error))
    } finally { setBusy(false) }
  }
  return <section className="panel">
    <h2>Linear referencing</h2>
    <p className="muted">Uses the fixed engineering calibration. Inventory interval edits affect QA and summaries.</p>
    <form className="toolbar" onSubmit={submit}>
      <label>Route<select name="route">{routes.map(id => <option key={id}>{id}</option>)}</select></label>
      <label>Operation<select value={mode} onChange={event => { setMode(event.target.value); setResult(null); setMarker(null); setError('') }}>
        <option value="locate">Milepoint to coordinate</option><option value="project">Coordinate to milepoint</option>
      </select></label>
      {mode === 'locate' ? <label>Milepoint<input name="milepoint" type="number" step="any" required /></label> : <>
        <label>Longitude<input name="lon" type="number" min="-180" max="180" step="any" required /></label>
        <label>Latitude<input name="lat" type="number" min="-90" max="90" step="any" required /></label>
      </>}
      <button className="primary" disabled={busy}>Calculate</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <p role="status">{result.milepoint.toFixed(4)} mi · {result.lon.toFixed(6)}°, {result.lat.toFixed(6)}° · {result.along_geometry_m.toFixed(2)} m along geometry{result.offset_m !== undefined && ` · ${result.offset_m.toFixed(2)} m offset`}</p>}
  </section>
}

function App() {
  const [fixture, setFixture] = useState('dirty')
  const [changes, setChanges] = useState<(Edit & { timestamp: string })[]>([])
  const [full, setFull] = useState<Bundle | null>(null)
  const [view, setView] = useState<Bundle | null>(null)
  const [selected, setSelected] = useState('SEG-001')
  const [route, setRoute] = useState('')
  const [kind, setKind] = useState('')
  const [tab, setTab] = useState('Inventory')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [marker, setMarker] = useState<Location | null>(null)
  const [importResult, setImportResult] = useState<(Bundle & { accepted: boolean }) | null>(null)

  async function refresh(nextFixture = fixture, nextChanges = changes, nextRoute = route, nextKind = kind, status = '') {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const request = { fixture: nextFixture, changes: nextChanges }
      const all = await post<Bundle>('preview', request)
      const filtered = nextRoute || nextKind
        ? await post<Bundle>('preview', { ...request, route_id: nextRoute, functional_class: nextKind }) : all
      setFull(all)
      setView(filtered)
      setFixture(nextFixture)
      setChanges(nextChanges)
      setRoute(nextRoute)
      setKind(nextKind)
      setSelected(current => filtered.segments.features.some(item => item.id === current) ? current : filtered.segments.features[0]?.id ?? '')
      setNotice(status)
    } catch (error) { setError(message(error)) }
    finally { setBusy(false) }
  }
  useEffect(() => { void refresh() }, [])

  const segment = view?.segments.features.find(feature => feature.id === selected)?.properties
  const routes = [...new Set(full?.segments.features.map(feature => feature.properties.route_id))]
  const impacted = new Set(view?.qa.flatMap(finding => finding.segment_ids))

  function choose(id: string) { setSelected(id); setTab('Inventory'); setNotice('') }
  function exports(bundle: Bundle, scope: string) {
    return <>
      <button onClick={() => download(scope + '-segments.geojson', 'application/geo+json', JSON.stringify(bundle.segments, null, 2))}>{scope} GeoJSON</button>
      <button onClick={() => download(scope + '-segments.csv', 'text/csv', bundle.csv)}>{scope} CSV</button>
    </>
  }
  async function validate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!full) return
    const fields = new FormData(event.currentTarget)
    const file = fields.get('file') as File
    setImportResult(null)
    setError('')
    setBusy(true)
    try {
      if (file.size > 500_000) throw new Error('File exceeds 500 kB.')
      setImportResult(await post<Bundle & { accepted: boolean }>('inventory/validate', {
        format: file.name.toLowerCase().endsWith('.csv') ? 'csv' : 'geojson', body: await file.text(),
        derive_measures: fields.has('derive'),
        metadata: {
          dataset_version: String(fields.get('version')), source: 'User-supplied synthetic import',
          license: String(fields.get('license')), schema_version: '1.0',
          generated_at: new Date().toISOString(), coordinate_reference_system: 'EPSG:4326',
        },
      }))
    } catch (error) { setError(message(error)) }
    finally { setBusy(false) }
  }

  return <>
    <header><div className="shell masthead"><div>
      <p className="eyebrow">Independent transportation research</p>
      <h1>Transportation GIS &amp; Roadway Analytics Lab</h1>
      <p className="muted">Engineering milepoints, roadway inventory and reproducible data quality checks.</p>
    </div><a href="/prototype/">Original prototype</a></div></header>
    <main className="shell">
      <p className="source">Synthetic Arizona-like study network · WGS84 / UTM zone 12N</p>
      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!view || !full ? <p role="status">{error ? <button onClick={() => void refresh()}>Retry loading data</button> : 'Loading synthetic inventory…'}</p> : <>
        <div className="metrics">
          <div><span>Segments</span><strong>{view.summary.segment_count}</strong></div>
          <div><span>Segment miles</span><strong>{view.summary.segment_miles.toFixed(2)}</strong></div>
          <div><span>QA findings</span><strong>{view.qa.length}</strong></div>
          <div><span>Completeness</span><strong>{view.summary.completeness_pct === null ? '—' : view.summary.completeness_pct + '%'}</strong></div>
        </div>
        <div className="workspace">
          <section className="panel">
            <h2>Roadway network</h2>
            <div className="toolbar filters">
              <label>Fixture<select value={fixture} disabled={busy} onChange={event => { setMarker(null); void refresh(event.target.value, [], '', '') }}>
                <option value="dirty">QA training fixture</option><option value="clean">Clean fixture</option>
              </select></label>
              <label>Route filter<select value={route} disabled={busy} onChange={event => void refresh(fixture, changes, event.target.value)}>
                <option value="">All routes</option>{routes.map(id => <option key={id}>{id}</option>)}
              </select></label>
              <label>Class filter<select value={kind} disabled={busy} onChange={event => void refresh(fixture, changes, route, event.target.value)}>
                <option value="">All classes</option>{classes.map(value => <option key={value}>{value}</option>)}
              </select></label>
              <button disabled={busy} onClick={() => { setMarker(null); void refresh(fixture, [], '', '', 'Synthetic fixture restored.') }}>Reset</button>
            </div>
            <RoadMap features={view.segments.features} baseline={full.segments.features} selected={selected} choose={choose} marker={marker} />
            {!view.segments.features.length && <p>No segments match the current filters.</p>}
          </section>
          <section className="panel">
            <div className="toolbar tabs" aria-label="Record workspace">{['Inventory', 'Quality', 'Reporting'].map(item =>
              <button key={item} aria-pressed={tab === item} onClick={() => setTab(item)}>{item}</button>)}</div>
            {tab === 'Inventory' && (segment ? <Editor key={segment.segment_id + JSON.stringify(segment)} segment={segment} busy={busy} save={edit => {
              const next = [...changes, { ...edit, timestamp: new Date().toISOString() }]
              void refresh(fixture, next, route, kind, 'Inventory saved for this page session. QA and reporting recalculated.')
            }} /> : <p>Select a segment to edit.</p>)}
            {tab === 'Quality' && <>
              <h2>Quality findings</h2>
              {view.qa.length ? <ul className="findings">{view.qa.map(item => <li key={item.id}>
                <strong>{item.rule_code}</strong><span>{item.severity} · {item.segment_ids.join(', ')}</span><p>{item.details}</p>
              </li>)}</ul> : <p>No findings in this view.</p>}
              <div className="toolbar">
                <button disabled={busy} onClick={() => void refresh(fixture, changes, route, kind, 'QA recalculated.')}>Re-run QA</button>
                <button onClick={() => download('qa-findings.csv', 'text/csv', [
                  'rule_code,severity,segment_ids,details', ...view.qa.map(item =>
                    [item.rule_code, item.severity, item.segment_ids.join(' / '), item.details]
                      .map(value => '"' + value.replaceAll('"', '""') + '"').join(',')),
                ].join('\r\n'))}>QA CSV</button>
              </div>
            </>}
            {tab === 'Reporting' && <>
              <h2>{view.summary.title}</h2><p className="muted">{view.summary.limitations}</p>
              {Object.entries(view.summary.groups).map(([key, entries]) => <details key={key}><summary>{groupLabels[key]}</summary>
                <ul>{entries.map(item => <li key={item.group}>{item.group} · {item.segments} segments · {item.segment_miles.toFixed(2)} mi</li>)}</ul>
              </details>)}
              <div className="toolbar export">
                {exports(view, 'Filtered')}{exports(full, 'Full')}
                <button onClick={() => download('technical-report.json', 'application/json',
                  JSON.stringify({ selection: { fixture, route, functional_class: kind }, summary: view.summary, qa: view.qa, audit: full.audit }, null, 2))}>Technical report JSON</button>
              </div>
            </>}
          </section>
        </div>
        <section className="panel">
          <h2>Roadway characteristics inventory</h2>
          <div className="table-scroll" tabIndex={0} aria-label="Scrollable roadway inventory">
            <table><thead><tr>{['Segment', 'Route', 'From (mi)', 'To (mi)', 'Class', 'Lanes', 'Surface', 'AADT', 'QA'].map(value => <th key={value} scope="col">{value}</th>)}</tr></thead>
              <tbody>{view.segments.features.map(({ properties: p, id }) => <tr key={id} className={selected === id ? 'active' : ''} onClick={() => choose(id)}>
                <td><button aria-label={'Table segment ' + id} aria-pressed={selected === id} onClick={event => { event.stopPropagation(); choose(id) }}>{id}</button></td>
                <td>{p.route_id}</td><td>{p.from_measure_mi.toFixed(2)}</td><td>{p.to_measure_mi.toFixed(2)}</td><td>{p.functional_class}</td>
                <td>{p.lanes}</td><td>{p.surface ?? 'Missing'}</td><td>{p.aadt.toLocaleString('en-US')}</td><td>{impacted.has(id) ? 'Review' : 'Pass'}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </section>
        <LrsTool routes={routes} setMarker={setMarker} />
        <section className="panel">
          <h2>Validate synthetic inventory</h2>
          <p className="muted">Use the exported CSV schema or WGS84 GeoJSON. Import validation runs on an isolated copy.</p>
          <form className="toolbar" onSubmit={validate}>
            <label>Inventory file<input name="file" type="file" accept=".csv,.geojson,.json" required /></label>
            <label>Source license<input name="license" defaultValue="CC0-1.0" required /></label>
            <label>Dataset version<input name="version" defaultValue={String(full.segments.metadata.dataset_version)} required /></label>
            <label className="checkbox"><input name="derive" type="checkbox" /> Derive absent milepoints in file order</label>
            <button disabled={busy}>Validate import</button>
          </form>
          {importResult && <div role="status"><p>{importResult.accepted ? 'Import accepted.' : 'Import has errors.'}</p>
            <ul>{importResult.qa.map(item => <li key={item.id}>{item.rule_code} · {item.segment_ids.join(', ')} · {item.details}</li>)}</ul>
            {importResult.accepted && <div className="toolbar">{exports(importResult, 'Validated')}</div>}
          </div>}
        </section>
        <section className="panel">
          <details><summary>Data provenance and calibration</summary>
            <dl>{Object.entries(full.segments.metadata).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{value}</dd></div>)}</dl>
          </details>
        </section>
      </>}
    </main>
  </>
}

createRoot(document.getElementById('root')!).render(<App />)
