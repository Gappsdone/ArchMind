import { useEffect, useRef } from 'react';
import cytoscape, { type Core } from 'cytoscape';
import type { GraphEdge, GraphNode } from './api';

export function GraphView({ nodes, edges, cycleNodes, cycleEdges, onNode, onEdge }: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  cycleNodes: Set<string>;
  cycleEdges: Set<string>;
  onNode: (id: string) => void;
  onEdge: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<Core | null>(null);
  const handlers = useRef({ onNode, onEdge });
  handlers.current = { onNode, onEdge };

  useEffect(() => {
    if (!container.current) return;
    const cy = cytoscape({
      container: container.current,
      elements: [],
      layout: { name: 'preset' },
      style: [
        { selector: 'node', style: { 'background-color': '#1e8091', label: 'data(label)', color: '#e9f5f3', 'font-size': 11, 'text-outline-color': '#102630', 'text-outline-width': 2, 'text-valign': 'bottom', 'text-margin-y': 9, width: 30, height: 30, 'border-width': 2, 'border-color': '#55b6b8' } },
        { selector: 'node.cycle', style: { 'background-color': '#dd9d39', 'border-color': '#ffd18a' } },
        { selector: 'edge', style: { width: 2, 'line-color': '#5c8990', 'target-arrow-color': '#5c8990', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', opacity: 0.75 } },
        { selector: 'edge.link', style: { 'line-color': '#9ccf80', 'target-arrow-color': '#9ccf80', 'line-style': 'solid' } },
        { selector: 'edge.build', style: { 'line-style': 'dashed' } },
        { selector: 'edge.cycle', style: { 'line-color': '#f2b155', 'target-arrow-color': '#f2b155', width: 4, opacity: 1 } },
        { selector: ':selected', style: { 'border-color': '#ffffff', 'line-color': '#ffffff', 'target-arrow-color': '#ffffff' } },
      ],
      minZoom: 0.15,
      maxZoom: 3,
    });
    cy.on('tap', 'node', event => handlers.current.onNode(event.target.id()));
    cy.on('tap', 'edge', event => handlers.current.onEdge(event.target.id()));
    graph.current = cy;
    return () => { cy.destroy(); graph.current = null; };
  }, []);

  useEffect(() => {
    const cy = graph.current;
    if (!cy) return;
    cy.elements().remove();
    cy.add([
      ...nodes.map(node => ({ data: { id: node.id, label: node.name }, classes: cycleNodes.has(node.id) ? 'cycle' : '' })),
      ...edges.map(edge => ({ data: { id: edge.id, source: edge.source_id, target: edge.target_id }, classes: `${edge.kind === 'LINKS_TO' ? 'link' : 'build'} ${cycleEdges.has(edge.id) ? 'cycle' : ''}` })),
    ]);
    cy.layout({ name: nodes.length < 40 ? 'breadthfirst' : 'cose', directed: true, animate: false, padding: 45 }).run();
    cy.fit(undefined, 45);
  }, [nodes, edges, cycleNodes, cycleEdges]);

  return <div className="graph-canvas" ref={container} role="img" aria-label="Interactive target dependency graph" />;
}
