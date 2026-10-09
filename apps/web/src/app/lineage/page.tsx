import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowRight, Database } from "lucide-react";

export const dynamic = "force-dynamic";

async function getLineage() {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
  
  try {
    const res = await fetch(`${apiUrl}/lineage`, { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to fetch lineage");
    const data = await res.json();
    return data.mappings || [];
  } catch (error) {
    console.error("Lineage API Error:", error);
    return null;
  }
}

export default async function LineagePage() {
  const mappings = await getLineage();
  if (!mappings) return <p role="alert">Mapping catalog is unavailable. No lineage data could be retrieved.</p>;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-5xl">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Data Lineage</h2>
        <p className="text-muted-foreground mt-1">
          Map business terms to FHIR fields. Open a source card in the question explorer to inspect its artifact hash, dataset, ingestion run and confirmed target.
        </p>
      </div>

      <Card className="bg-card/50 border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="w-5 h-5 text-muted-foreground" />
            Semantic Mapping Catalog
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead>Business Domain</TableHead>
                <TableHead>Business Entity</TableHead>
                <TableHead className="w-8"></TableHead>
                <TableHead>FHIR Resource</TableHead>
                <TableHead>FHIR Element</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mappings.map((m: any, i: number) => (
                <TableRow key={i} className="border-border hover:bg-muted/50">
                  <TableCell className="font-medium text-foreground">{m.business_domain}</TableCell>
                  <TableCell className="text-muted-foreground">{m.business_entity}</TableCell>
                  <TableCell className="text-muted-foreground"><ArrowRight className="w-4 h-4" /></TableCell>
                  <TableCell className="font-mono text-blue-600 dark:text-blue-400 text-sm">{m.fhir_resource}</TableCell>
                  <TableCell className="font-mono text-muted-foreground text-sm">{m.fhir_element}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
