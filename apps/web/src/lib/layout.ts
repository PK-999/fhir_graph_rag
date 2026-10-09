import dagre from "dagre";
import { type Node, type Edge, Position } from "@xyflow/react";

export const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = "TB") => {
  const dagreGraph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  const isHorizontal = direction === "LR";
  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 100 });

  nodes.forEach((node) => {
    // We assume default dimensions for layouting
    dagreGraph.setNode(node.id, { width: 250, height: 100 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const newNode = {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      // Shift to center the node relative to dagre's coordinates
      position: {
        x: nodeWithPosition.x - 250 / 2,
        y: nodeWithPosition.y - 100 / 2,
      },
    };
    return newNode as Node;
  });

  return { nodes: newNodes, edges };
};

export const getRadialLayoutedElements = (nodes: Node[], edges: Edge[], centerNodeId: string) => {
  const radius = 300;

  const otherNodes = nodes.filter(n => n.id !== centerNodeId);

  const angleStep = (2 * Math.PI) / (otherNodes.length || 1);

  const newNodes = nodes.map((node) => {
    if (node.id === centerNodeId) {
      return {
        ...node,
        position: { x: 0, y: 0 },
        targetPosition: Position.Top,
        sourcePosition: Position.Bottom,
      };
    } else {
      const idx = otherNodes.findIndex(n => n.id === node.id);
      const angle = idx * angleStep - Math.PI / 2; // Start from top
      return {
        ...node,
        position: {
          x: radius * Math.cos(angle),
          y: radius * Math.sin(angle),
        },
        targetPosition: Position.Top,
        sourcePosition: Position.Bottom,
      };
    }
  });

  return { nodes: newNodes, edges };
};
