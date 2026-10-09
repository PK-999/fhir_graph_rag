import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Users, FileText, Pill, Stethoscope, Scissors, Network, Link2 } from "lucide-react";

export const dynamic = "force-dynamic";

async function getDashboardSummary() {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

  try {
    const res = await fetch(`${apiUrl}/dashboard/summary`, { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to fetch dashboard summary");
    return res.json();
  } catch (error) {
    console.error("Dashboard API Error:", error);
    return null;
  }
}

export default async function DashboardPage() {
  const summary = await getDashboardSummary();

  if (!summary) return <div role="alert">Graph service is unavailable. Counts could not be retrieved.</div>;

  const metrics = [
    { title: "Total Patients", value: summary.patients, icon: Users, color: "text-blue-500" },
    { title: "Encounters", value: summary.encounters, icon: Activity, color: "text-emerald-500" },
    { title: "Conditions", value: summary.conditions, icon: Stethoscope, color: "text-rose-500" },
    { title: "Observations", value: summary.observations, icon: FileText, color: "text-amber-500" },
    { title: "Medications", value: summary.medications, icon: Pill, color: "text-purple-500" },
    { title: "Procedures", value: summary.procedures, icon: Scissors, color: "text-cyan-500" },
  ];

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Knowledge Graph Dashboard</h2>
        <p className="text-muted-foreground mt-2">
          Overview of the synthetic healthcare dataset and graph topology.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {metrics.map((metric, i) => (
          <Card key={i} className="bg-card/60 border-border/50 backdrop-blur-xl rounded-2xl shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 overflow-hidden relative group">
            <div className="absolute inset-0 bg-gradient-to-br from-transparent to-muted/20 opacity-0 group-hover:opacity-100 transition-opacity" />
            <CardHeader className="flex flex-row items-center justify-between pb-2 relative z-10">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {metric.title}
              </CardTitle>
              <div className={`p-2 rounded-xl bg-background shadow-sm border border-border/50 ${metric.color}`}>
                <metric.icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent className="relative z-10">
              <div className="text-3xl font-bold text-foreground tracking-tight">{metric.value.toLocaleString()}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8">
        <h3 className="text-xl font-semibold mb-4 text-foreground">Graph Topology</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="bg-card/60 border-border/50 backdrop-blur-xl rounded-2xl shadow-sm hover:shadow-md transition-all duration-300">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Nodes</CardTitle>
              <div className="p-2 rounded-xl bg-background shadow-sm border border-border/50 text-muted-foreground">
                <Network className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-foreground tracking-tight">{summary.graph_nodes.toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card className="bg-card/60 border-border/50 backdrop-blur-xl rounded-2xl shadow-sm hover:shadow-md transition-all duration-300">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Relationships</CardTitle>
              <div className="p-2 rounded-xl bg-background shadow-sm border border-border/50 text-muted-foreground">
                <Link2 className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-foreground tracking-tight">{summary.graph_edges.toLocaleString()}</div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
