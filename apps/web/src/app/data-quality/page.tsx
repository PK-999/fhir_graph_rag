import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2 } from "lucide-react";

export const dynamic = "force-dynamic";

async function getDQSummary() {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

  try {
    const res = await fetch(`${apiUrl}/data-quality/summary`, { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to fetch DQ summary");
    return res.json();
  } catch (error) {
    console.error("DQ API Error:", error);
    return { latest_run: null, results: [], error: "Quality service is unavailable. No run outcome could be retrieved." };
  }
}

export default async function DataQualityPage() {
  const { latest_run, results, error } = await getDQSummary();

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Data Quality</h2>
        <p className="text-muted-foreground mt-1">
          Monitor the integrity and validation metrics of the generated dataset.
        </p>
      </div>

      {error && <p role="alert" className="text-red-600">{error}</p>}
      {!error && !latest_run && <p>No recorded pipeline runs yet. Run the pipeline to populate quality results.</p>}
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="bg-card/50 border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Latest Ingestion Run</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold truncate text-foreground" title={latest_run?.id}>
              {latest_run?.id?.split('-')[0] || 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {latest_run?.start_time ? new Date(latest_run.start_time).toLocaleString() : 'Unknown'}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Overall Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              {latest_run?.status === "success" && <CheckCircle2 className="w-6 h-6" />}
              {error ? "Unavailable" : latest_run?.status || "No run"}
            </div>
          </CardContent>
        </Card>
      </div>

      {latest_run?.error_message && <p role="alert" className="text-red-600">{latest_run.error_message}</p>}
      {latest_run?.config_snapshot?.dataset_hash && <p className="font-mono text-xs break-all text-muted-foreground">Dataset SHA-256: {latest_run.config_snapshot.dataset_hash}</p>}
      <Card className="bg-card/50 border-border">
        <CardHeader>
          <CardTitle>Validation Rules</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead>Rule Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Rule Outcome</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                    No data quality results found.
                  </TableCell>
                </TableRow>
              ) : (
                results.map((r: any, i: number) => (
                  <TableRow key={i} className="border-border hover:bg-muted/50">
                    <TableCell className="font-medium text-foreground">{r.rule_name}</TableCell>
                    <TableCell>
                      {r.status === 'pass' && <Badge className="bg-emerald-100/50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-500 dark:border-emerald-500/20">Pass</Badge>}
                      {r.status === 'fail' && <Badge className="bg-rose-100/50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-500 dark:border-rose-500/20">Fail</Badge>}
                      {r.status === 'warning' && <Badge className="bg-amber-100/50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:text-amber-500 dark:border-amber-500/20">Warning</Badge>}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-full bg-secondary h-2 rounded-full overflow-hidden w-24">
                          <div
                            className={`h-full ${r.pass_rate >= 99 ? 'bg-emerald-500' : r.pass_rate >= 90 ? 'bg-amber-500' : 'bg-rose-500'}`}
                            style={{ width: `${r.pass_rate === 100 ? "Pass" : "Fail"}` }}
                          />
                        </div>
                        <span className="text-sm text-muted-foreground">{r.pass_rate === 100 ? "Pass" : "Fail"}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {JSON.stringify(r.details)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
