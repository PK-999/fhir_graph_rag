"use client";

import { useEffect, useState } from "react";
import { X, ChevronRight, Code2 } from "lucide-react";
import { getNodeDisplayName } from "@/lib/graph";

interface NodeData {
  id: string;
  labels: string[];
  properties: Record<string, any>;
}

interface ExploreCategory {
  relationship: string;
  neighbor_type: string;
  count: number;
}

export function NodeInspector({
  node,
  onClose,
  onExpand,
}: {
  node: NodeData | null;
  onClose: () => void;
  onExpand?: (nodeId: string, relationship: string, targetLabel: string) => void;
}) {
  const [categories, setCategories] = useState<ExploreCategory[]>([]);
  const [showJson, setShowJson] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!node) return;
    setShowJson(false);

    async function loadExplore() {
      setLoading(true);
      try {
        const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
        const res = await fetch(`${url}/graph/explore/${encodeURIComponent(node!.id)}`);
        const data = await res.json();
        setCategories(data.categories || []);
      } catch (err) {
        console.error("Explore fetch error:", err);
        setCategories([]);
      } finally {
        setLoading(false);
      }
    }
    loadExplore();
  }, [node]);

  if (!node) return null;

  const label = node.labels[0] || "Unknown";
  const props = node.properties;
  const displayName = getNodeDisplayName(node.id, props);

  // Human-readable relationship labels
  const REL_LABELS: Record<string, string> = {
    SUBJECT: "Subject",
    ENCOUNTER: "Encounter",
    SERVICE_PROVIDER: "Service Provider",
    PARTICIPANT_INDIVIDUAL: "Participant",
    REASON_REFERENCE: "Reason",
    PRESCRIBER: "Prescriber",
    REQUESTER: "Requester",
    PERFORMER_ACTOR: "Performer",
    RESULT: "Result",
    HAS_MEMBER: "Member",
  };

  return (
    <div className="w-80 border-l border-border bg-card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider shrink-0">{label}</span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Display name */}
        <div>
          <h3 className="text-lg font-semibold text-foreground leading-tight">{displayName}</h3>
          <span className="text-xs text-muted-foreground font-mono">{node.id}</span>
        </div>

        {/* Key properties */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Properties</h4>
          <div className="space-y-1.5">
            {Object.entries(props)
              .filter(([k]) => k !== "id")
              .map(([key, value]) => (
                <div key={key} className="flex justify-between items-start text-sm gap-2">
                  <span className="text-muted-foreground shrink-0">{key.replace(/_/g, " ")}</span>
                  <span className="text-foreground text-right truncate">{String(value ?? "—")}</span>
                </div>
              ))}
          </div>
        </div>

        {/* Exploration categories */}
        {categories.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Explore</h4>
            <div className="space-y-1">
              {categories.map((cat, i) => (
                <button
                  key={i}
                  onClick={() => onExpand?.(node.id, cat.relationship, cat.neighbor_type)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm
                             bg-secondary border border-border hover:bg-secondary/80
                             transition-colors text-left group"
                >
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                  <span className="text-foreground flex-1">
                    {REL_LABELS[cat.relationship] || cat.relationship}
                    {cat.neighbor_type && (
                      <span className="text-muted-foreground ml-1">→ {cat.neighbor_type}</span>
                    )}
                  </span>
                  <span className="text-muted-foreground font-mono text-xs">{cat.count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="text-muted-foreground text-sm animate-pulse">Loading relationships...</div>
        )}
      </div>

      {/* Footer actions */}
      <div className="p-3 border-t border-border flex gap-2 shrink-0">
        <button
          onClick={() => setShowJson(!showJson)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium
                     bg-accent text-accent-foreground border border-border hover:bg-accent/80 transition-colors"
        >
          <Code2 className="w-3.5 h-3.5" />
          {showJson ? "Hide properties" : "Graph properties"}
        </button>
      </div>

      {/* JSON drawer */}
      {showJson && (
        <div className="border-t border-border max-h-64 overflow-y-auto p-3 bg-secondary/50">
          <pre className="text-xs text-muted-foreground font-mono whitespace-pre-wrap break-all">
            {JSON.stringify(props, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
