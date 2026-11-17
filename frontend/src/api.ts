export type Project = { id: string; name: string; root_path: string };
export type Snapshot = { id: string; project_id: string; status: string; cmake_config: string; created_at: string; git_commit: string | null };
export type GraphNode = { id: string; kind: string; name: string; stable_key: string };
export type GraphEdge = { id: string; source_id: string; target_id: string; kind: string; origin: string; evidence_count: number; metadata_json?: string };
export type Subgraph = { nodes: GraphNode[]; edges: GraphEdge[]; next_cursor: string | null; truncated: boolean };
export type Evidence = { kind: string; file_path: string | null; line_start: number | null; description: string | null; metadata_json: string };
export type EvidenceResponse = { id: string; source_id: string; target_id: string; kind: string; origin: string; evidence: Evidence[]; diagnostics: string[] };
export type SourceExcerpt = { path: string; requested_line: number; lines: { number: number; text: string }[] };
export type GraphScope = 'target' | 'symbol' | 'namespace';
export type NodeDetail = GraphNode & { metadata: { qualified_name?: string; file_path?: string | null; line?: number | null; is_abstract?: boolean } };
export type SymbolTrace = { items: { id: string; source_name: string; target_name: string; kind: string; evidence: Evidence[] }[]; diagnostics: string[]; truncated: boolean };
export type Impact = { items: { id: string; name: string; stable_key: string; distance: number; via: string; targets: { id: string; name: string }[] }[]; truncated: boolean; affected_targets: { id: string; name: string }[] };

const BASE = '/api/v1';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  projects: () => request<{ items: Project[] }>('/projects'),
  snapshots: (id: string) => request<{ items: Snapshot[] }>(`/projects/${encodeURIComponent(id)}/snapshots`),
  subgraph: (id: string, options: { centerId?: string; cursor?: string; limit?: number; scope?: GraphScope } = {}) => {
    const params = new URLSearchParams();
    params.set('limit', String(options.limit ?? 100));
    if (options.centerId) params.set('center_id', options.centerId);
    if (options.cursor) params.set('cursor', options.cursor);
    if (options.scope) params.set('scope', options.scope);
    return request<Subgraph>(`/snapshots/${encodeURIComponent(id)}/subgraph?${params}`);
  },
  cycles: (id: string, kind = 'BUILD_DEPENDS_ON') => request<{ items: string[][] }>(`/snapshots/${encodeURIComponent(id)}/cycles?kind=${encodeURIComponent(kind)}`),
  node: (id: string, nodeId: string) => request<NodeDetail>(`/snapshots/${encodeURIComponent(id)}/nodes/${encodeURIComponent(nodeId)}`),
  targetSymbols: (id: string, targetId: string, cursor?: string) => request<{ items: GraphNode[]; truncated: boolean; next_cursor: string | null }>(`/snapshots/${encodeURIComponent(id)}/targets/${encodeURIComponent(targetId)}/symbols${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`),
  symbolTrace: (id: string, edgeId: string) => request<SymbolTrace>(`/snapshots/${encodeURIComponent(id)}/edges/${encodeURIComponent(edgeId)}/symbol-trace`),
  impact: (id: string, symbolId: string) => request<Impact>(`/snapshots/${encodeURIComponent(id)}/impact?symbol_id=${encodeURIComponent(symbolId)}`),
  evidence: (id: string, edgeId: string) => request<EvidenceResponse>(`/snapshots/${encodeURIComponent(id)}/edges/${encodeURIComponent(edgeId)}/evidence`),
  source: (id: string, path: string, line: number) => {
    const params = new URLSearchParams({ path, line: String(line) });
    return request<SourceExcerpt>(`/snapshots/${encodeURIComponent(id)}/source?${params}`);
  },
};

export function mergeGraph(current: Subgraph, incoming: Subgraph): Subgraph {
  const nodes = new Map(current.nodes.map(node => [node.id, node]));
  const edges = new Map(current.edges.map(edge => [edge.id, edge]));
  incoming.nodes.forEach(node => nodes.set(node.id, node));
  incoming.edges.forEach(edge => edges.set(edge.id, edge));
  return { nodes: [...nodes.values()], edges: [...edges.values()], next_cursor: incoming.next_cursor ?? current.next_cursor, truncated: current.truncated || incoming.truncated };
}

export function cycleSets(cycles: string[][]): Set<string>[] {
  return cycles.map(cycle => new Set(cycle));
}

export function edgeInCycle(edge: GraphEdge, cycles: Set<string>[]): boolean {
  return cycles.some(cycle => cycle.has(edge.source_id) && cycle.has(edge.target_id));
}

export function relationshipLabel(edge: GraphEdge): string {
  if (edge.kind === 'BUILD_DEPENDS_ON') return 'BUILD';
  if (edge.kind === 'LINKS_TO') return 'LINK';
  if (edge.kind === 'DEPENDS_ON') return 'DERIVED';
  if (edge.kind === 'USES_TYPE') {
    try {
      const subtype = JSON.parse(edge.metadata_json ?? '{}').clang_uml_type;
      if (typeof subtype === 'string') return subtype.toUpperCase();
    } catch { /* Legacy metadata: show the generic relationship. */ }
  }
  return edge.kind.replaceAll('_', ' ');
}
