"use client";

import { useRef, useState, useCallback } from "react";
import { GraphViewer, GraphViewerRef, SelectedNode } from "@/components/GraphViewer";
import { NodeInspector } from "@/components/NodeInspector";

export function PatientGraphTab({ patientId }: { patientId: string }) {
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const graphRef = useRef<GraphViewerRef>(null);

  const handleNodeSelect = useCallback((node: SelectedNode | null) => {
    setSelectedNode(node);
  }, []);

  const handleExpand = useCallback((nodeId: string, relationship: string, targetLabel: string) => {
    graphRef.current?.expandNode(nodeId, relationship, targetLabel);
  }, []);

  return (
    <div className="flex h-full rounded-md overflow-hidden border border-border">
      {/* Graph canvas */}
      <div className="flex-1 min-w-0 relative">
        <GraphViewer
          ref={graphRef}
          initialNodeId={`Patient/${patientId}`}
          onNodeSelect={handleNodeSelect}
        />


      </div>

      {/* Inspector panel — slides in when a node is selected */}
      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
          onExpand={handleExpand}
        />
      )}
    </div>
  );
}
