import { Suspense } from "react";
import { GraphPageClient } from "./GraphPageClient";

export default async function GraphPage({
  searchParams,
}: {
  searchParams: Promise<{ node?: string }>
}) {
  const { node = "Patient/p-000001" } = await searchParams;

  return (
    <div className="space-y-6 h-full flex flex-col animate-in fade-in duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Graph Explorer</h2>
        <p className="text-muted-foreground mt-1">
          Interactive visualization of the Neo4j Knowledge Graph. Click a node to inspect its properties and explore relationships.
        </p>
      </div>

      <div className="flex-1 min-h-0 pb-4">
        <Suspense fallback={<div className="h-full bg-secondary animate-pulse rounded-md" />}>
          <GraphPageClient initialNodeId={node} />
        </Suspense>
      </div>
    </div>
  );
}
