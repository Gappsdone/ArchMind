import { useEffect, useMemo, useState } from 'react';
import { api, cycleSets, edgeInCycle, mergeGraph, relationshipLabel, type EvidenceResponse, type GraphEdge, type GraphNode, type GraphScope, type Impact, type NodeDetail, type Project, type Snapshot, type SourceExcerpt, type Subgraph, type SymbolTrace } from './api';
import { GraphView } from './GraphView';

const EMPTY: Subgraph = { nodes: [], edges: [], next_cursor: null, truncated: false };
type Selection = { snapshotId: string; edgeId: string; sourceId: string; targetId: string; relationship: string };

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [snapshotId, setSnapshotId] = useState('');
  const [scope, setScope] = useState<GraphScope>('target');
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [graph, setGraph] = useState<Subgraph>(EMPTY);
  const [initialGraph, setInitialGraph] = useState<Subgraph>(EMPTY);
  const [cycles, setCycles] = useState<string[][]>([]);
  const [showBuild, setShowBuild] = useState(true);
  const [showLinks, setShowLinks] = useState(true);
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<GraphNode[]>([]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [targetSymbols, setTargetSymbols] = useState<GraphNode[]>([]);
  const [targetSymbolsCursor, setTargetSymbolsCursor] = useState<string | null>(null);
  const [impact, setImpact] = useState<Impact | null>(null);
  const [symbolTrace, setSymbolTrace] = useState<SymbolTrace | null>(null);
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
    setNodeDetail(null); setTargetSymbols([]); setTargetSymbolsCursor(null); setImpact(null); setSymbolTrace(null);
    setEvidence(null); setSource(null); setMatches([]); setQuery('');
    if (!snapshotId) return;
    let active = true;
    setBusy(true); setError('');
    const cycleKind = scope === 'target' ? 'BUILD_DEPENDS_ON' : scope === 'symbol' ? 'USES_TYPE' : 'DEPENDS_ON';
    Promise.all([api.subgraph(snapshotId, { scope, centerId: focusNodeId ?? undefined }), api.cycles(snapshotId, cycleKind)]).then(([subgraph, cycleResult]) => {
      if (!active) return;
      setGraph(subgraph); setInitialGraph(subgraph); setCycles(cycleResult.items);
      if (focusNodeId) {
        const focused = focusNodeId;
        setSelectedNode(focused); setFocusNodeId(null);
        api.node(snapshotId, focused).then(detail => { if (active) setNodeDetail(detail); }).catch(err => { if (active) setError(String(err)); });
        if (scope === 'symbol') api.impact(snapshotId, focused).then(result => { if (active) setImpact(result); }).catch(err => { if (active) setError(String(err)); });
      }
    }).catch(err => { if (active) setError(String(err)); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [snapshotId, scope]);

  useEffect(() => {
    if (!snapshotId || query.trim().length < 2) { setMatches([]); return; }
    let active = true;
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ kind: scope === 'target' ? 'CMAKE_TARGET' : scope === 'namespace' ? 'NAMESPACE' : 'CLASS', name: query.trim(), limit: '20' });
      fetch(`/api/v1/snapshots/${encodeURIComponent(snapshotId)}/nodes?${params}`)
        .then(response => { if (!response.ok) throw new Error('Target search failed'); return response.json(); })
        .then(result => { if (active) setMatches(result.items); })
        .catch(err => { if (active) setError(String(err)); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [snapshotId, scope, query]);

  const cycleGroups = useMemo(() => cycleSets(cycles), [cycles]);
  const cycleNodes = useMemo(() => new Set(cycles.flat()), [cycles]);
  const visibleEdges = useMemo(() => graph.edges.filter(edge =>
    scope !== 'target' || (edge.kind === 'BUILD_DEPENDS_ON' && showBuild) || (edge.kind === 'LINKS_TO' && showLinks)),
  [graph.edges, scope, showBuild, showLinks]);
  const visibleNodeIds = useMemo(() => new Set(visibleEdges.flatMap(edge => [edge.source_id, edge.target_id])), [visibleEdges]);
  const visibleNodes = useMemo(() => graph.nodes.filter(node => scope !== 'target' || visibleNodeIds.has(node.id) || node.id === selectedNode || graph.edges.length === 0), [graph.nodes, graph.edges.length, visibleNodeIds, selectedNode, scope]);
  const cycleEdges = useMemo(() => new Set(visibleEdges.filter(edge => edgeInCycle(edge, cycleGroups)).map(edge => edge.id)), [visibleEdges, cycleGroups]);
  const nodeNames = useMemo(() => new Map(graph.nodes.map(node => [node.id, node.name])), [graph.nodes]);
  const selectedSnapshot = snapshots.find(item => item.id === snapshotId);

  async function expand(nodeId: string) {
    if (!snapshotId) return;
    setSelectedNode(nodeId); setSelection(null); setEvidence(null); setSymbolTrace(null);
    setNodeDetail(null); setTargetSymbols([]); setTargetSymbolsCursor(null); setImpact(null); setBusy(true); setError('');
    try {
      const [incoming, detail] = await Promise.all([
        api.subgraph(snapshotId, { centerId: nodeId, limit: 100, scope }), api.node(snapshotId, nodeId),
      ]);
      setGraph(current => mergeGraph(current, incoming));
      setNodeDetail(detail);
      if (scope === 'target') {
        const page = await api.targetSymbols(snapshotId, nodeId);
        setTargetSymbols(page.items); setTargetSymbolsCursor(page.next_cursor);
      }
      if (scope === 'symbol') setImpact(await api.impact(snapshotId, nodeId));
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }

  async function more() {
    if (!snapshotId || !graph.next_cursor) return;
    setBusy(true); setError('');
    try {
      const incoming = await api.subgraph(snapshotId, { cursor: graph.next_cursor, scope });
      setGraph(current => ({ ...mergeGraph(current, incoming), next_cursor: incoming.next_cursor }));
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  }

  async function selectEdge(edge: GraphEdge) {
    if (!snapshotId) return;
    setSelection({ snapshotId, edgeId: edge.id, sourceId: edge.source_id, targetId: edge.target_id, relationship: edge.kind });
    setSelectedNode(null); setNodeDetail(null); setTargetSymbols([]); setTargetSymbolsCursor(null); setImpact(null);
    setEvidence(null); setSource(null); setSymbolTrace(null); setError('');
    try {
      const [details, trace] = await Promise.all([
        api.evidence(snapshotId, edge.id),
        scope === 'target' ? api.symbolTrace(snapshotId, edge.id) : Promise.resolve(null),
      ]);
      setEvidence(details); setSymbolTrace(trace);
    }
    catch (err) { setError(String(err)); }
  }

  async function openSource(path: string, line: number | null) {
    if (!snapshotId) return;
    setSource(null); setError('');
    try { setSource(await api.source(snapshotId, path, line ?? 1)); }
    catch (err) { setError(String(err)); }
  }

  function focusSymbol(id: string) {
    setFocusNodeId(id);
    setScope('symbol');
  }

  async function moreTargetSymbols() {
    if (!snapshotId || !selectedNode || !targetSymbolsCursor) return;
    try {
      const page = await api.targetSymbols(snapshotId, selectedNode, targetSymbolsCursor);
      setTargetSymbols(current => [...current, ...page.items]);
      setTargetSymbolsCursor(page.next_cursor);
    } catch (err) { setError(String(err)); }
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

        <div className="section-label section-gap">GRAPH LEVEL</div>
        <label htmlFor="graph-level">Explore</label>
        <select id="graph-level" value={scope} onChange={event => { setFocusNodeId(null); setScope(event.target.value as GraphScope); }}>
          <option value="target">CMake targets</option>
          <option value="namespace">Namespaces</option>
          <option value="symbol">C++ classes</option>
        </select>

        <div className="section-label section-gap">FIND {scope === 'target' ? 'TARGET' : scope === 'namespace' ? 'NAMESPACE' : 'CLASS'}</div>
        <input aria-label="Search targets" placeholder="Search across snapshot…" value={query} onChange={event => setQuery(event.target.value)} disabled={!snapshotId} />
        {query.length >= 2 && <div className="search-results" aria-label="Search results">
          {matches.length === 0 ? <span className="muted">No matching targets</span> : matches.map(node => <button type="button" key={node.id} onClick={() => { void expand(node.id); setQuery(''); }}>{node.name}<small>{node.stable_key}</small></button>)}
        </div>}

        {scope === 'target' && <><div className="section-label section-gap">RELATIONSHIPS</div>
        <label className="check-row" title="CMake build-order relationship; directness may be unknown"><input type="checkbox" checked={showBuild} onChange={event => setShowBuild(event.target.checked)} /><span className="legend-line build-line" /> Build dependencies</label>
        <label className="check-row"><input type="checkbox" checked={showLinks} onChange={event => setShowLinks(event.target.checked)} /><span className="legend-line link-line" /> Verified links</label>
        </>}
        <div className="sidebar-foot"><span className="cycle-swatch" /> Cycle members <small>{scope === 'target' ? 'Build-order edges may include transitive relationships. Only evidenced links are marked as verified.' : 'Semantic edges come from clang-uml. Namespace dependencies are derived from class relationships.'}</small></div>
      </aside>

      <main className="main-area">
        <div className="view-heading"><div><div className="eyebrow">{scope === 'target' ? 'TARGET ARCHITECTURE' : scope === 'symbol' ? 'C++ SEMANTICS' : 'NAMESPACE ARCHITECTURE'}</div><h1>Dependency explorer</h1><p>{scope === 'target' ? 'Inspect the build graph, then select a relationship to trace its evidence.' : 'Explore source-grounded C++ relationships in this snapshot.'}</p></div><div className="view-count"><strong>{graph.nodes.length}</strong><span>{scope === 'target' ? 'targets' : scope === 'symbol' ? 'classes' : 'namespaces'} in view</span><strong>{graph.edges.length}</strong><span>relationships</span></div></div>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="graph-panel">
          <div className="panel-toolbar"><span>{busy ? 'Loading graph…' : graph.truncated ? 'Scoped view · more targets available' : 'Scoped view'}</span><div><span>{cycles.length} cycle{cycles.length === 1 ? '' : 's'}</span>{graph.next_cursor && <button type="button" onClick={() => void more()} disabled={busy}>Load more targets</button>}{selectedNode && <button type="button" onClick={() => void expand(selectedNode)} disabled={busy}>Expand selected</button>}{(selectedNode || graph.nodes.length > initialGraph.nodes.length) && <button type="button" onClick={() => { setGraph(initialGraph); setSelectedNode(null); }}>Reset scope</button>}</div></div>
          {snapshotId && graph.nodes.length > 0 ? <GraphView nodes={visibleNodes} edges={visibleEdges} cycleNodes={cycleNodes} cycleEdges={cycleEdges} onNode={id => void expand(id)} onEdge={id => { const edge = graph.edges.find(item => item.id === id); if (edge) void selectEdge(edge); }} /> : <div className="empty-state">{snapshotId && scope !== 'target' ? 'No semantic graph in this snapshot. Reanalyze with --semantic and a compile_commands.json build.' : 'Register and analyze a CMake project with the CLI to begin exploring.'}</div>}
          <div className="graph-hint">Scroll to zoom · drag to pan · select a node to expand · select an edge for evidence</div>
        </div>
        <div className="relationship-panel"><div className="panel-title"><h2>Relationships in view</h2><span>{visibleEdges.length} shown</span></div><div className="relationship-list">
          {visibleEdges.length === 0 ? <div className="muted list-empty">No relationships match this view.</div> : visibleEdges.slice(0, 120).map(edge => <button type="button" className={`relationship-row ${selection?.edgeId === edge.id ? 'active' : ''}`} key={edge.id} onClick={() => void selectEdge(edge)}><span className={`edge-tag ${edge.kind === 'LINKS_TO' || edge.kind === 'USES_TYPE' ? 'link-tag' : ''}`}>{relationshipLabel(edge)}</span><strong>{nodeNames.get(edge.source_id) ?? 'Unknown'}</strong><span className="arrow">→</span><strong>{nodeNames.get(edge.target_id) ?? 'Unknown'}</strong>{cycleEdges.has(edge.id) && <span className="cycle-chip">Cycle</span>}<small>{edge.evidence_count} evidence</small></button>)}
        </div>{visibleEdges.length > 120 && <div className="list-foot">Showing first 120 relationships. Expand or filter the graph to narrow the view.</div>}</div>
      </main>

      <aside className="inspector"><div className="section-label">INSPECTOR</div>{selection ? <>
        <div className="inspector-heading"><div className="eyebrow">SELECTED RELATIONSHIP</div><h2>{nodeNames.get(selection.sourceId) ?? 'Source'} <span>→</span> {nodeNames.get(selection.targetId) ?? 'Target'}</h2><span className="relationship-type">{selection.relationship.replaceAll('_', ' ')}</span></div>
        <div className="inspector-block"><h3>Provenance</h3>{!evidence ? <p className="muted">Loading evidence…</p> : <>{evidence.evidence.length === 0 && <p className="muted">No source provenance is available for this edge.</p>}{evidence.evidence.map((item, index) => <div className="evidence-card" key={`${item.kind}-${index}`}><div className="evidence-head"><strong>{item.kind.replaceAll('_', ' ')}</strong><span>{JSON.parse(item.metadata_json || '{}').confidence ?? 'unknown'}</span></div><p>{item.description}</p>{item.file_path ? <button type="button" className="source-link" onClick={() => void openSource(item.file_path!, item.line_start)}>{item.file_path}{item.line_start ? `:${item.line_start}` : ' · line unavailable'} ↗</button> : <span className="muted">Source location unavailable</span>}</div>)}{evidence.diagnostics.map((item, index) => <p className="muted" key={index}>{item}</p>)}</>}</div>
        {symbolTrace && <div className="inspector-block"><h3>Cross-target C++ relationships</h3>{symbolTrace.items.map(item => <div className="evidence-card" key={item.id}><strong>{item.source_name} → {item.target_name}</strong><p>{item.kind.replaceAll('_', ' ')}</p>{item.evidence.map((proof, index) => proof.file_path ? <button type="button" className="source-link" key={index} onClick={() => void openSource(proof.file_path!, proof.line_start)}>{proof.file_path}{proof.line_start ? `:${proof.line_start}` : ' · line unavailable'} ↗</button> : <span className="muted" key={index}>Exact relationship line unavailable</span>)}</div>)}{symbolTrace.diagnostics.map((item, index) => <p className="muted" key={index}>{item}</p>)}</div>}
        {source && <div className="inspector-block source-block"><div className="source-title"><h3>Source excerpt</h3><button type="button" onClick={() => setSource(null)} aria-label="Close source excerpt">×</button></div><div className="source-path">{source.path}</div><pre>{source.lines.map(line => <div className={line.number === source.requested_line ? 'highlight-line' : ''} key={line.number}><span>{line.number}</span>{line.text}</div>)}</pre></div>}
        <div className="inspector-foot">Snapshot-bound evidence · no AI inference</div>
      </> : selectedNode && nodeDetail ? <>
        <div className="inspector-heading"><div className="eyebrow">SELECTED {nodeDetail.kind.replaceAll('_', ' ')}</div><h2>{nodeDetail.metadata.qualified_name ?? nodeDetail.name}</h2></div>
        {nodeDetail.metadata.file_path && <div className="inspector-block"><h3>Declaration</h3><button type="button" className="source-link" onClick={() => void openSource(nodeDetail.metadata.file_path!, nodeDetail.metadata.line ?? null)}>{nodeDetail.metadata.file_path}{nodeDetail.metadata.line ? `:${nodeDetail.metadata.line}` : ' · line unavailable'} ↗</button></div>}
        {scope === 'target' && <div className="inspector-block"><h3>Classes owned by target</h3>{targetSymbols.length === 0 ? <p className="muted">No source-owned classes found. Headers not listed by CMake may have unknown target ownership.</p> : targetSymbols.map(item => <button type="button" className="symbol-button" key={item.id} onClick={() => focusSymbol(item.id)}>{item.name}<span>Explore →</span></button>)}{targetSymbolsCursor && <button type="button" className="symbol-button" onClick={() => void moreTargetSymbols()}>Load more classes</button>}</div>}
        {scope === 'symbol' && <div className="inspector-block"><h3>Potentially affected classes</h3>{impact?.items.length ? impact.items.map(item => <button type="button" className="symbol-button" key={item.id} onClick={() => void expand(item.id)}>{item.name}<span>{item.targets.map(target => target.name).join(', ') || 'target unknown'} · {item.distance} hop{item.distance === 1 ? '' : 's'}</span></button>) : <p className="muted">No incoming class relationships found within the current bound.</p>}</div>}
        {source && <div className="inspector-block source-block"><div className="source-title"><h3>Source excerpt</h3><button type="button" onClick={() => setSource(null)} aria-label="Close source excerpt">×</button></div><div className="source-path">{source.path}</div><pre>{source.lines.map(line => <div className={line.number === source.requested_line ? 'highlight-line' : ''} key={line.number}><span>{line.number}</span>{line.text}</div>)}</pre></div>}
      </> : <div className="inspector-empty"><div className="inspector-icon">↗</div><h2>Select a relationship</h2><p>Choose an edge on the graph or in the relationship list to inspect its source provenance.</p></div>}</aside>
    </div>
  </div>;
}
