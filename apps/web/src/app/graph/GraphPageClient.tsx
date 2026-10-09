"use client";

import { useState, useCallback, useRef } from "react";
import { GraphViewer, SelectedNode, SelectedEdge, GraphViewerRef } from "@/components/GraphViewer";
import { NodeInspector } from "@/components/NodeInspector";
import { EdgeInspector } from "@/components/EdgeInspector";
import { TimelineView } from "@/components/TimelineView";
import { PatientSidebar, ViewMode } from "@/components/PatientSidebar";

export function GraphPageClient({ initialNodeId }: { initialNodeId: string }) {
  const [activeNodeId, setActiveNodeId] = useState(initialNodeId);
  const [viewMode, setViewMode] = useState<ViewMode>("patient-360");
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdge | null>(null);
  const graphRef = useRef<GraphViewerRef>(null);

  const handleNodeSelect = useCallback((node: SelectedNode | null) => {
    setSelectedNode(node);
    if (node) setSelectedEdge(null);
  }, []);

  const handleEdgeSelect = useCallback((edge: SelectedEdge | null) => {
    setSelectedEdge(edge);
    if (edge) setSelectedNode(null);
  }, []);

  const handleExpand = useCallback((nodeId: string, relationship: string, targetLabel: string) => {
    graphRef.current?.expandNode(nodeId, relationship, targetLabel);
  }, []);

  const handleStorySelect = useCallback((story: string) => {
    if (!graphRef.current) return;
    if (story === "Patient Overview") {
       graphRef.current.resetHighlight();
    } else if (story === "Conditions and Labs") {
       graphRef.current.highlightByType(["Condition", "MedicationRequest", "Observation"]);
    } else if (story === "Encounters and Procedures") {
       graphRef.current.highlightByType(["Encounter", "Procedure"]);
    } else if (story === "Medication History") {
       graphRef.current.highlightByType(["MedicationRequest"]);
    } else {
       graphRef.current.resetHighlight();
    }
  }, []);

  const isPatientActive = activeNodeId.startsWith("Patient/");
  const patientId = isPatientActive ? activeNodeId.split("/")[1] : null;

  return (
    <div className="flex h-full border-t border-border bg-background">
      {isPatientActive && patientId && (
        <PatientSidebar
          patientId={patientId}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onStorySelect={handleStorySelect}
        />
      )}

      <div className="flex flex-col flex-1 min-w-0 bg-muted/20">
        <div className="flex flex-1 min-h-0 relative">
          <div className="flex-1 min-w-0 p-4">
            <div className="h-full rounded-xl overflow-hidden border border-border bg-card shadow-sm">
              <GraphViewer
                ref={graphRef}
                initialNodeId={initialNodeId}
                viewMode={viewMode}
                onNodeSelect={handleNodeSelect}
                onEdgeSelect={handleEdgeSelect}
                onActiveNodeChange={setActiveNodeId}
              />
            </div>
          </div>

          {selectedNode && (
            <div className="w-80 shrink-0 border-l border-border bg-card">
              <NodeInspector
                node={selectedNode}
                onClose={() => setSelectedNode(null)}
                onExpand={handleExpand}
              />
            </div>
          )}

          {selectedEdge && (
            <div className="w-[400px] shrink-0 border-l border-border bg-card">
              <EdgeInspector
                edge={selectedEdge}
                onClose={() => setSelectedEdge(null)}
              />
            </div>
          )}
        </div>

        {isPatientActive && patientId && viewMode !== "explorer" && (
          <div className="h-72 border-t border-border bg-card shrink-0 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] relative z-10">
            <div className="bg-muted/50 border-b border-border px-4 py-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight">Clinical Journey Timeline</h3>
              <span className="text-xs text-muted-foreground">Patient: {patientId}</span>
            </div>
            <div className="h-[calc(100%-40px)] overflow-hidden">
              <TimelineView patientId={patientId} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
