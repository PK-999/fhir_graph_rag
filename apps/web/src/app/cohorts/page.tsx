"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, X, Play, Loader2 } from "lucide-react";

const ALL_CONDITIONS = [
  { code: "195662009", name: "Acute respiratory infection" },
  { code: "414916001", name: "Obesity (disorder)" },
  { code: "195967001", name: "Asthma" },
  { code: "44465007", name: "Sprain of ankle" },
  { code: "414545008", name: "Ischemic heart disease" },
  { code: "55822004", name: "Hyperlipidemia" },
  { code: "13645005", name: "Chronic obstructive pulmonary disease" },
  { code: "44054006", name: "Type 2 diabetes mellitus" },
  { code: "709044004", name: "Chronic kidney disease" },
  { code: "38341003", name: "Hypertension" },
  { code: "77386006", name: "Patient currently pregnant" }
];

function ConditionAutocomplete({ value, onChange, onRemove }: { value: string, onChange: (val: string) => void, onRemove: () => void }) {
  const [query, setQuery] = useState(() => ALL_CONDITIONS.find(c => c.code === value)?.name || value);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setQuery(ALL_CONDITIONS.find(c => c.code === value)?.name || value);
  }, [value]);

  const results = ALL_CONDITIONS.filter(c =>
    c.name.toLowerCase().includes(query.toLowerCase()) ||
    c.code.includes(query)
  );

  return (
    <div className="flex items-center gap-2 relative w-full">
      <div className="relative w-full">
        <Input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            onChange(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 200)}
          placeholder="e.g. Diabetes"
          className="bg-background border-input w-full"
        />
        {isOpen && results.length > 0 && (
          <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-md shadow-lg max-h-60 overflow-auto">
            {results.map(r => (
              <div
                key={r.code}
                className="p-2 hover:bg-muted cursor-pointer text-sm"
                onMouseDown={(e) => e.preventDefault()} // Prevent blur before click fires
                onClick={() => {
                  setQuery(r.name);
                  onChange(r.code);
                  setIsOpen(false);
                }}
              >
                <div className="font-medium text-foreground">{r.name}</div>
                <div className="text-xs text-muted-foreground">Code: {r.code}</div>
              </div>
            ))}
          </div>
        )}
      </div>
      <Button variant="ghost" size="icon" onClick={onRemove}>
        <X className="h-4 w-4 text-muted-foreground hover:text-destructive" />
      </Button>
    </div>
  );
}

export default function CohortBuilderPage() {
  const [conditions, setConditions] = useState<string[]>([]);
  const [minAge, setMinAge] = useState<string>("");
  const [maxAge, setMaxAge] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleQuery = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
      const payload = {
        conditions: conditions.filter(c => c.trim() !== ""),
        min_age: minAge ? parseInt(minAge) : null,
        max_age: maxAge ? parseInt(maxAge) : null,
      };

      const res = await fetch(`${url}/cohorts/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data.detail === "string"
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join("; ")
            : "";
        throw new Error(detail || "Could not complete the cohort query. Please try again.");
      }
      setResult(data);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Could not complete the cohort query. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Cohort Builder</h2>
        <p className="text-muted-foreground mt-1">
          Dynamically query the Knowledge Graph using criteria filters.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <Card className="bg-card/50 border-border lg:col-span-1 h-fit">
          <CardHeader>
            <CardTitle>Filters</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Conditions (SNOMED Code or Name)</label>
              <div className="mt-2 space-y-2">
                {conditions.map((c, i) => (
                  <ConditionAutocomplete
                    key={i}
                    value={c}
                    onChange={(val) => {
                      const newC = [...conditions];
                      newC[i] = val;
                      setConditions(newC);
                    }}
                    onRemove={() => setConditions(conditions.filter((_, idx) => idx !== i))}
                  />
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-dashed border-border bg-transparent hover:bg-secondary"
                  onClick={() => setConditions([...conditions, ""])}
                >
                  <Plus className="h-4 w-4 mr-2" /> Add Condition
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-4 border-t border-border">
              <div>
                <label className="text-sm font-medium text-muted-foreground">Min Age</label>
                <Input
                  type="number"
                  value={minAge}
                  onChange={(e) => setMinAge(e.target.value)}
                  placeholder="e.g. 18"
                  className="mt-1 bg-background border-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">Max Age</label>
                <Input
                  type="number"
                  value={maxAge}
                  onChange={(e) => setMaxAge(e.target.value)}
                  placeholder="e.g. 65"
                  className="mt-1 bg-background border-input"
                />
              </div>
            </div>

            <Button
              className="w-full mt-6 bg-blue-600 hover:bg-blue-700"
              onClick={handleQuery}
              disabled={loading}
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
              Execute Query
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Results {result && <span className="ml-2 text-muted-foreground text-sm font-normal">({result.count} matched)</span>}</CardTitle>
          </CardHeader>
          <CardContent>
            {error && <p role="alert" className="mb-4 text-sm text-destructive">{error}</p>}
            {result?.query && (
              <div className="mb-4 p-3 bg-muted rounded-md border border-border overflow-x-auto text-xs font-mono text-muted-foreground">
                {result.query}
              </div>
            )}

            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead>ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>DOB</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!result ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center h-32 text-muted-foreground">
                        Run a query to see results
                      </TableCell>
                    </TableRow>
                  ) : !result.patients || result.patients.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center h-32 text-muted-foreground text-red-500">
                        {result.detail ? JSON.stringify(result.detail) : "No patients matched your criteria"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    result.patients.map((p: any) => (
                      <TableRow key={p.id} className="border-border hover:bg-muted/50">
                        <TableCell className="font-medium text-blue-600 dark:text-blue-400">{p.id.replace('Patient/', '')}</TableCell>
                        <TableCell>{p.name}</TableCell>
                        <TableCell>{p.birthDate}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
