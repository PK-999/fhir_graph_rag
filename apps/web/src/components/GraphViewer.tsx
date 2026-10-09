"use client";

import { useEffect, useState, useCallback, useImperativeHandle, forwardRef } from "react";
import { ReactFlow, useNodesState, useEdgesState, Background, Controls, MiniMap, Node, Edge, MarkerType } from "@xyflow/react";
import '@xyflow/react/dist/style.css';

import { ClinicalNode } from "./nodes/ClinicalNode";
import { getLayoutedElements, getRadialLayoutedElements } from "../lib/layout";
import { getNodeDisplayName, getGraphEdgeId, type GraphEdgeIdentity } from "../lib/graph";
import { ViewMode } from "./PatientSidebar";

export interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

export interface SelectedNode {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

export interface SelectedEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  sourceNodeLabel: string;
  targetNodeLabel: string;
}

export interface GraphViewerRef {
  expandNode: (nodeId: string, relationship: string, targetLabel: string) => Promise<void>;
  highlightElements: (nodeIds: string[], edgeIds: string[]) => void;
  highlightByType: (types: string[]) => void;
  resetHighlight: () => void;
}

interface GraphViewerProps {
  initialNodeId: string;
  onNodeSelect?: (node: SelectedNode | null) => void;
  onEdgeSelect?: (edge: SelectedEdge | null) => void;
  onActiveNodeChange?: (nodeId: string) => void;
  viewMode?: ViewMode;
}

const nodeTypes = {
  clinical: ClinicalNode,
};

export const GraphViewer = forwardRef<GraphViewerRef, GraphViewerProps>(({ initialNodeId, onNodeSelect, onEdgeSelect, onActiveNodeChange, viewMode = "explorer" }, ref) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(false);
  const [nodeIdInput, setNodeIdInput] = useState(initialNodeId);
  const [activeNodeId, setActiveNodeId] = useState(initialNodeId);
  const [depth, setDepth] = useState(1);
  const [truncated, setTruncated] = useState(false);

  const formatGraph = (dataNodes: GraphNode[], dataEdges: GraphEdgeIdentity[]) => {
    const rfNodes: Node[] = dataNodes.map((n) => ({
      id: n.id,
      type: "clinical",
      position: { x: 0, y: 0 }, // Set by layout later
      data: {
        ...n.properties,
        properties: n.properties,
        id: n.id,
        type: n.labels[0] || "Unknown",
        label: getNodeDisplayName(n.id, n.properties),
      },
    }));

    const rfEdges: Edge[] = dataEdges.map((e) => ({
      id: getGraphEdgeId(e),
      source: e.source,
      target: e.target,
      label: e.type,
      type: 'smoothstep',
      animated: false,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 15,
        height: 15,
        color: '#64748b',
      },
      style: {
        strokeWidth: 2,
        stroke: '#64748b',
      },
      labelStyle: { fill: '#64748b', fontWeight: 600, fontSize: 10 },
      labelBgStyle: { fill: 'transparent' },
    }));

    return { rfNodes, rfEdges };
  };

  const fetchGraph = useCallback(async (id: string, d: number, mode: ViewMode) => {
    if (!id) return;
    setLoading(true);
    try {
      const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

      let endpoint = `/graph/neighbors/${encodeURIComponent(id)}?depth=${d}`;
      if (mode === "patient-360" && id.startsWith("Patient/")) {
        endpoint = `/patients/${encodeURIComponent(id.split("/")[1])}/summary-graph`;
      } else if (mode === "clinical-journey") {
        endpoint = `/graph/neighbors/${encodeURIComponent(id)}?depth=1`;
      }

      const res = await fetch(`${url}${endpoint}`);
      const data = await res.json();
      setTruncated(data.truncated || false);

      const { rfNodes, rfEdges } = formatGraph(data.nodes || [], data.edges || []);

      let layouted;
      if (mode === "patient-360" && id.startsWith("Patient/")) {
        layouted = getRadialLayoutedElements(rfNodes, rfEdges, id);
      } else {
        layouted = getLayoutedElements(rfNodes, rfEdges, "TB");
      }

      setNodes(layouted.nodes);
      setEdges(layouted.edges);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useImperativeHandle(ref, () => ({
    expandNode: async (id: string, relationship: string, targetLabel: string) => {
      setLoading(true);
      try {
        const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
        const res = await fetch(`${url}/graph/explore/${encodeURIComponent(id)}/expand?relationship=${encodeURIComponent(relationship)}&target_label=${encodeURIComponent(targetLabel)}`);
        const data = await res.json();

        const { rfNodes, rfEdges } = formatGraph(data.nodes || [], data.edges || []);

        // Merge with existing
        const newNodes = [...nodes];
        const newEdges = [...edges];

        rfNodes.forEach((n) => {
          if (!newNodes.find(existing => existing.id === n.id)) {
            newNodes.push(n);
          }
        });

        const edgeIds = new Set(newEdges.map((edge) => edge.id));
        rfEdges.forEach((e) => {
          if (!edgeIds.has(e.id)) {
            newEdges.push(e);
            edgeIds.add(e.id);
          }
        });

        const layouted = getLayoutedElements(newNodes, newEdges, "TB");
        setNodes(layouted.nodes);
        setEdges(layouted.edges);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    highlightElements: (nodeIds: string[], edgeIds: string[]) => {
      setNodes((nds) => nds.map((n) => ({ ...n, style: { opacity: nodeIds.includes(n.id) ? 1 : 0.2 } })));
      setEdges((eds) => eds.map((e) => ({ ...e, style: { opacity: edgeIds.includes(e.id) ? 1 : 0.2 } })));
    },
    highlightByType: (types: string[]) => {
      setNodes((nds) => {
        const highlightedIds = nds.filter((n) => types.includes(n.data.type as string)).map(n => n.id);
        return nds.map((n) => ({ ...n, style: { opacity: highlightedIds.includes(n.id) ? 1 : 0.2 } }));
      });
      // A more robust implementation would also highlight connected edges
    },
    resetHighlight: () => {
      setNodes((nds) => nds.map((n) => ({ ...n, style: { opacity: 1 } })));
      setEdges((eds) => eds.map((e) => ({ ...e, style: { opacity: 1 } })));
    }
  }));

  useEffect(() => {
    fetchGraph(activeNodeId, depth, viewMode);
    onActiveNodeChange?.(activeNodeId);
  }, [activeNodeId, depth, viewMode, fetchGraph, onActiveNodeChange]);

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    onNodeSelect?.({
      id: node.id,
      labels: [node.data.type as string],
      properties: node.data.properties as GraphNode["properties"],
    });
    onEdgeSelect?.(null);
  };

  const handleEdgeClick = (_: React.MouseEvent, edge: Edge) => {
    const sourceNode = nodes.find(n => n.id === edge.source);
    const targetNode = nodes.find(n => n.id === edge.target);
    onEdgeSelect?.({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label as string,
      sourceNodeLabel: sourceNode?.data?.label as string || edge.source,
      targetNodeLabel: targetNode?.data?.label as string || edge.target,
    });
    onNodeSelect?.(null);
  };

  const handlePaneClick = () => {
    onNodeSelect?.(null);
    onEdgeSelect?.(null);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      <div className="flex-1 min-h-[500px] w-full bg-slate-50 dark:bg-zinc-950 relative rounded-2xl border border-border/50 shadow-sm overflow-hidden">

        {/* Floating Toolbar */}
        <div className="absolute top-4 left-4 z-20 flex flex-wrap gap-2 items-center bg-background/80 backdrop-blur-xl p-2 rounded-xl border border-border/50 shadow-sm">
          <input
            value={nodeIdInput}
            onChange={(e) => setNodeIdInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') setActiveNodeId(nodeIdInput);
            }}
            placeholder="e.g., Patient/p-000001"
            className="bg-background/50 border border-border/50 px-3 py-1.5 rounded-lg text-sm w-56 text-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all"
          />
          <select
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            className="bg-background/50 border border-border/50 px-3 py-1.5 rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all cursor-pointer"
          >
            <option value={1}>Depth 1</option>
            <option value={2}>Depth 2</option>
            <option value={3}>Depth 3</option>
          </select>
          <button
            onClick={() => setActiveNodeId(nodeIdInput)}
            className="bg-primary/90 hover:bg-primary text-primary-foreground px-4 py-1.5 rounded-lg text-sm font-medium transition-all shadow-sm"
          >
            Load
          </button>
          {truncated && (
            <span className="text-xs text-amber-600 dark:text-amber-500 bg-amber-500/10 px-2.5 py-1.5 rounded-lg border border-amber-500/20 font-medium">
              Results truncated
            </span>
          )}
        </div>

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-10">
            <div className="text-blue-500 font-medium animate-pulse">Layouting graph...</div>
          </div>
        )}

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          onPaneClick={handlePaneClick}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.1}
        >
          <Background color="#cbd5e1" gap={16} />
          <Controls />
          <MiniMap zoomable pannable className="rounded-xl overflow-hidden border border-border/50" />
        </ReactFlow>
      </div>
    </div>
  );
});

GraphViewer.displayName = "GraphViewer";
