import { useEffect, useMemo, useState } from 'react';
import { api, cycleSets, edgeInCycle, mergeGraph, type EvidenceResponse, type GraphEdge, type GraphNode, type Project, type Snapshot, type SourceExcerpt, type Subgraph } from './api';
import { GraphView } from './GraphView';

const EMPTY: Subgraph = { nodes: [], edges: [], next_cursor: null, truncated: false };
type Selection = { snapshotId: string; edgeId: string; sourceId: string; targetId: string; relationship: string };

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotId, setSnapshotId] = useState('');
  const [graph, setGraph] = useState<Subgraph>(EMPTY);
  const [initialGraph, setInitialGraph] = useState<Subgraph>(EMPTY);
  const [cycles, setCycles] = useState<string[][]>([]);
  const [showBuild, setShowBuild] = useState(true);
  const [showLinks, setShowLinks] = useState(true);
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<GraphNode[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [source, setSource] = useState<SourceExcerpt | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.projects().then(result => {
      setProjects(result.items);
      setProjectId(result.items[0]?.id ?? '');
    }).catch(err => setError(String(err)));
  }, []);

  useEffect(() => {
    if (!projectId) { setSnapshots([]); setSnapshotId(''); return; }
    let active = true;
    setSnapshotId('');
    api.snapshots(projectId).then(result => {
      if (!active) return;
      const complete = result.items.filter(item => item.status === 'complete');
      setSnapshots(complete);
      setSnapshotId(complete[0]?.id ?? '');
    }).catch(err => { if (active) setError(String(err)); });
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    setGraph(EMPTY); setInitialGraph(EMPTY); setCycles([]); setSelection(null); setSelectedNode(null);
    setEvidence(null); setSource(null); setMatches([]); setQuery('');
    if (!snapshotId) return;
    let active = true;
    setBusy(true); setError('');
    Promise.all([api.subgraph(snapshotId), api.cycles(snapshotId)]).then(([subgraph, cycleResult]) => {
      if (!active) return;
      setGraph(subgraph); setInitialGraph(subgraph); setCycles(cycleResult.items);
    }).catch(err => { if (active) setError(String(err)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [snapshotId]);

  useEffect(() => {
    if (!snapshotId || query.trim().length < 2) { setMatches([]); return; }
    let active = true;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ kind: 'CMAKE_TARGET', name: query.trim(), limit: '20' });
      fetch(`/api/v1/snapshots/${encodeURIComponent(snapshotId)}/nodes?${params}`)
        .then(response => { if (!response.ok) throw new Error('Target search failed'); return response.json(); })
        .then(result => { if (active) setMatches(result.items); })
        .catch(err => { if (active) setError(String(err)); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [snapshotId, query]);

  const cycleGroups = useMemo(() => cycleSets(cycles), [cycles]);
  const cycleNodes = useMemo(() => new Set(cycles.flat()), [cycles]);
  const visibleEdges = useMemo(() => graph.edges.filter(edge =>
    (edge.kind === 'BUILD_DEPENDS_ON' && showBuild) || (edge.kind === 'LINKS_TO' && showLinks)),
  [graph.edges, showBuild, showLinks]);
  const visibleNodeIds = useMemo(() => new Set(visibleEdges.flatMap(edge => [edge.source_id, edge.target_id])), [visibleEdges]);
  const visibleNodes = useMemo(() => graph.nodes.filter(node => visibleNodeIds.has(node.id) || node.id === selectedNode || graph.edges.length === 0), [graph.nodes, graph.edges.length, visibleNodeIds, selectedNode]);
  const cycleEdges = useMemo(() => new Set(visibleEdges.filter(edge => edgeInCycle(edge, cycleGroups)).map(edge => edge.id)), [visibleEdges, cycleGroups]);
  const nodeNames = useMemo(() => new Map(graph.nodes.map(node => [node.id, node.name])), [graph.nodes]);
  const selectedSnapshot = snapshots.find(item => item.id === snapshotId);

  async function expand(nodeId: string) {
    if (!snapshotId) return;
    setSelectedNode(nodeId); setBusy(true); setError('');
    try {
      const incoming = await api.subgraph(snapshotId, { centerId: nodeId, limit: 100 });
      setGraph(current => mergeGraph(current, incoming));
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }

  async function more() {
    if (!snapshotId || !graph.next_cursor) return;
    setBusy(true); setError('');
    try {
      const incoming = await api.subgraph(snapshotId, { cursor: graph.next_cursor });
      setGraph(current => ({ ...mergeGraph(current, incoming), next_cursor: incoming.next_cursor }));
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }

  async function selectEdge(edge: GraphEdge) {
    if (!snapshotId) return;
    setSelection({ snapshotId, edgeId: edge.id, sourceId: edge.source_id, targetId: edge.target_id, relationship: edge.kind });
    setEvidence(null); setSource(null); setError('');
    try { setEvidence(await api.evidence(snapshotId, edge.id)); }
    catch (err) { setError(String(err)); }
  }

  async function openSource(path: string, line: number | null) {
    if (!snapshotId) return;
    setSource(null); setError('');
    try { setSource(await api.source(snapshotId, path, line ?? 1)); }
    catch (err) { setError(String(err)); }
  }

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">A<span>·</span>M</span><div><strong>ArchMind</strong><small>Architecture intelligence</small></div></div>
      <div className="topbar-note">LOCAL · READ-ONLY EXPLORER <span className="status-dot" /></div>
    </header>
    <div className="workspace">
      <aside className="sidebar">
        <div className="section-label">WORKSPACE</div>
        <label htmlFor="project">Project</label>
        <select id="project" value={projectId} onChange={event => setProjectId(event.target.value)}>
          {projects.length === 0 && <option value="">No projects registered</option>}
          {projects.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
        </select>
        <label htmlFor="snapshot">Snapshot</label>
        <select id="snapshot" value={snapshotId} onChange={event => setSnapshotId(event.target.value)}>
          {snapshots.length === 0 && <option value="">No completed snapshots</option>}
          {snapshots.map(item => <option value={item.id} key={item.id}>{new Date(item.created_at).toLocaleString()} · {item.cmake_config || 'Default'}</option>)}
        </select>
        {selectedSnapshot && <div className="snapshot-meta"><div>Configuration <strong>{selectedSnapshot.cmake_config || 'Default'}</strong></div><div>Revision <strong title={selectedSnapshot.git_commit ?? 'Untracked'}>{selectedSnapshot.git_commit?.slice(0, 8) ?? 'Untracked'}</strong></div></div>}

        <div className="section-label section-gap">FIND TARGET</div>
        <input aria-label="Search targets" placeholder="Search across snapshot…" value={query} onChange={event => setQuery(event.target.value)} disabled={!snapshotId} />
        {query.length >= 2 && <div className="search-results" aria-label="Search results">
          {matches.length === 0 ? <span className="muted">No matching targets</span> : matches.map(node => <button type="button" key={node.id} onClick={() => { void expand(node.id); setQuery(''); }}>{node.name}<small>{node.stable_key}</small></button>)}
        </div>}

        <div className="section-label section-gap">RELATIONSHIPS</div>
        <label className="check-row" title="CMake build-order relationship; directness may be unknown"><input type="checkbox" checked={showBuild} onChange={event => setShowBuild(event.target.checked)} /><span className="legend-line build-line" /> Build dependencies</label>
        <label className="check-row"><input type="checkbox" checked={showLinks} onChange={event => setShowLinks(event.target.checked)} /><span className="legend-line link-line" /> Verified links</label>
        <div className="sidebar-foot"><span className="cycle-swatch" /> Cycle members <small>Build-order edges may include transitive relationships. Only evidenced links are marked as verified.</small></div>
      </aside>

      <main className="main-area">
        <div className="view-heading"><div><div className="eyebrow">TARGET ARCHITECTURE</div><h1>Dependency explorer</h1><p>Inspect the build graph, then select a relationship to trace its evidence.</p></div><div className="view-count"><strong>{graph.nodes.length}</strong><span>targets in view</span><strong>{graph.edges.length}</strong><span>relationships</span></div></div>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="graph-panel">
          <div className="panel-toolbar"><span>{busy ? 'Loading graph…' : graph.truncated ? 'Scoped view · more targets available' : 'Scoped view'}</span><div><span>{cycles.length} cycle{cycles.length === 1 ? '' : 's'}</span>{graph.next_cursor && <button type="button" onClick={() => void more()} disabled={busy}>Load more targets</button>}{selectedNode && <button type="button" onClick={() => void expand(selectedNode)} disabled={busy}>Expand selected</button>}{(selectedNode || graph.nodes.length > initialGraph.nodes.length) && <button type="button" onClick={() => { setGraph(initialGraph); setSelectedNode(null); }}>Reset scope</button>}</div></div>
          {snapshotId ? <GraphView nodes={visibleNodes} edges={visibleEdges} cycleNodes={cycleNodes} cycleEdges={cycleEdges} onNode={id => void expand(id)} onEdge={id => { const edge = graph.edges.find(item => item.id === id); if (edge) void selectEdge(edge); }} /> : <div className="empty-state">Register and analyze a CMake project with the CLI to begin exploring.</div>}
          <div className="graph-hint">Scroll to zoom · drag to pan · select a node to expand · select an edge for evidence</div>
        </div>
        <div className="relationship-panel"><div className="panel-title"><h2>Relationships in view</h2><span>{visibleEdges.length} shown</span></div><div className="relationship-list">
          {visibleEdges.length === 0 ? <div className="muted list-empty">No relationships match these filters.</div> : visibleEdges.slice(0, 120).map(edge => <button type="button" className={`relationship-row ${selection?.edgeId === edge.id ? 'active' : ''}`} key={edge.id} onClick={() => void selectEdge(edge)}><span className={`edge-tag ${edge.kind === 'LINKS_TO' ? 'link-tag' : ''}`}>{edge.kind === 'LINKS_TO' ? 'LINK' : 'BUILD'}</span><strong>{nodeNames.get(edge.source_id) ?? 'Unknown'}</strong><span className="arrow">→</span><strong>{nodeNames.get(edge.target_id) ?? 'Unknown'}</strong>{cycleEdges.has(edge.id) && <span className="cycle-chip">Cycle</span>}<small>{edge.evidence_count} evidence</small></button>)}
        </div>{visibleEdges.length > 120 && <div className="list-foot">Showing first 120 relationships. Expand or filter the graph to narrow the view.</div>}</div>
      </main>

      <aside className="inspector"><div className="section-label">INSPECTOR</div>{selection ? <>
        <div className="inspector-heading"><div className="eyebrow">SELECTED RELATIONSHIP</div><h2>{nodeNames.get(selection.sourceId) ?? 'Source'} <span>→</span> {nodeNames.get(selection.targetId) ?? 'Target'}</h2><span className="relationship-type">{selection.relationship.replaceAll('_', ' ')}</span></div>
        <div className="inspector-block"><h3>Provenance</h3>{!evidence ? <p className="muted">Loading evidence…</p> : <>{evidence.evidence.length === 0 && <p className="muted">No source provenance is available for this edge.</p>}{evidence.evidence.map((item, index) => <div className="evidence-card" key={`${item.kind}-${index}`}><div className="evidence-head"><strong>{item.kind.replaceAll('_', ' ')}</strong><span>{JSON.parse(item.metadata_json || '{}').confidence ?? 'unknown'}</span></div><p>{item.description}</p>{item.file_path ? <button type="button" className="source-link" onClick={() => void openSource(item.file_path!, item.line_start)}>{item.file_path}{item.line_start ? `:${item.line_start}` : ' · line unavailable'} ↗</button> : <span className="muted">Source location unavailable</span>}</div>)}{evidence.diagnostics.map((item, index) => <p className="muted" key={index}>{item}</p>)}</>}</div>
        {source && <div className="inspector-block source-block"><div className="source-title"><h3>Source excerpt</h3><button type="button" onClick={() => setSource(null)} aria-label="Close source excerpt">×</button></div><div className="source-path">{source.path}</div><pre>{source.lines.map(line => <div className={line.number === source.requested_line ? 'highlight-line' : ''} key={line.number}><span>{line.number}</span>{line.text}</div>)}</pre></div>}
        <div className="inspector-foot">Snapshot-bound evidence · no AI inference</div>
      </> : <div className="inspector-empty"><div className="inspector-icon">↗</div><h2>Select a relationship</h2><p>Choose an edge on the graph or in the relationship list to inspect its source provenance.</p></div>}</aside>
    </div>
  </div>;
}
