import test from 'node:test';
import assert from 'node:assert/strict';
import { cycleSets, edgeInCycle, mergeGraph, type GraphEdge, type Subgraph } from '../src/api';

const a = { id: 'a', kind: 'CMAKE_TARGET', name: 'A', stable_key: 'A' };
const b = { id: 'b', kind: 'CMAKE_TARGET', name: 'B', stable_key: 'B' };
const c = { id: 'c', kind: 'CMAKE_TARGET', name: 'C', stable_key: 'C' };
const ab: GraphEdge = { id: 'ab', source_id: 'a', target_id: 'b', kind: 'BUILD_DEPENDS_ON', origin: 'declared', evidence_count: 1 };
const bc: GraphEdge = { id: 'bc', source_id: 'b', target_id: 'c', kind: 'LINKS_TO', origin: 'declared', evidence_count: 1 };

test('expansion merges overlapping graph observations without duplicate nodes or edges', () => {
  const overview: Subgraph = { nodes: [a, b], edges: [ab], next_cursor: 'B', truncated: true };
  const neighborhood: Subgraph = { nodes: [b, c], edges: [ab, bc], next_cursor: null, truncated: false };
  const merged = mergeGraph(overview, neighborhood);
  assert.deepEqual(merged.nodes.map(node => node.id), ['a', 'b', 'c']);
  assert.deepEqual(merged.edges.map(edge => edge.id), ['ab', 'bc']);
  assert.equal(merged.next_cursor, 'B');
});

test('cycle styling applies only to edges within the same SCC', () => {
  const groups = cycleSets([['a', 'b'], ['c', 'd']]);
  assert.equal(edgeInCycle(ab, groups), true);
  assert.equal(edgeInCycle(bc, groups), false);
});
