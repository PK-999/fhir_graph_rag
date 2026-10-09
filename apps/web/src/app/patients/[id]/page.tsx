import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, UserCircle, Calendar, Activity, Pill, Stethoscope, Scissors, Clock, Network, Code2 } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

// Client components loaded dynamically
import { PatientGraphTab } from "./PatientGraphTab";
import { TimelineView } from "@/components/TimelineView";

async function getPatientDetail(id: string) {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

  try {
    const res = await fetch(`${apiUrl}/patients/${id}`, { cache: 'no-store' });
    if (!res.ok) throw new Error("Patient not found");
    return res.json();
  } catch (error) {
    console.error("Detail API Error:", error);
    return null;
  }
}

async function getPatientResource(id: string) {
  const apiUrl = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
  try {
    const res = await fetch(`${apiUrl}/resources/Patient/${encodeURIComponent(id)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function PatientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params;
  const p = await getPatientDetail(id);

  if (!p) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        <h2 className="text-xl">Patient not found</h2>
        <Link href="/patients" className="text-blue-600 dark:text-blue-500 hover:underline mt-4 inline-block">
          Return to Registry
        </Link>
      </div>
    );
  }

  const cleanId = p.id.replace("Patient/", "");
  const fhirResource = await getPatientResource(cleanId);
  const counts = p.counts || {
    encounters: p.encounters?.length || 0,
    conditions: p.conditions?.length || 0,
    medications: p.medications?.length || 0,
    observations: p.observations?.length || 0,
    procedures: p.procedures?.length || 0,
  };

  // Domain summary cards for the Story view
  const domainCards = [
    { label: "Encounters", count: counts.encounters, icon: Calendar, color: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/20" },
    { label: "Conditions", count: counts.conditions, icon: Activity, color: "text-rose-600 dark:text-rose-400", bg: "bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20" },
    { label: "Medications", count: counts.medications, icon: Pill, color: "text-purple-600 dark:text-purple-400", bg: "bg-purple-50 dark:bg-purple-500/10 border-purple-200 dark:border-purple-500/20" },
    { label: "Observations", count: counts.observations, icon: Stethoscope, color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20" },
    { label: "Procedures", count: counts.procedures, icon: Scissors, color: "text-orange-600 dark:text-orange-400", bg: "bg-orange-50 dark:bg-orange-500/10 border-orange-200 dark:border-orange-500/20" },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <Link href="/patients" className="text-muted-foreground hover:text-foreground flex items-center text-sm mb-4 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back to Registry
        </Link>
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center">
            <UserCircle className="w-10 h-10 text-muted-foreground" />
          </div>
          <div>
            <h2 className="text-3xl font-bold tracking-tight">{p.name}</h2>
            <div className="flex items-center gap-3 mt-1">
              <Badge variant="outline" className="bg-secondary border-border">{cleanId}</Badge>
              <span className="text-sm text-muted-foreground capitalize">{p.gender}</span>
              <span className="text-sm text-muted-foreground">DOB: {p.birthDate}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Progressive Disclosure Tabs: Story → Timeline → Graph → FHIR ── */}
      <Tabs defaultValue="story" className="w-full mt-8">
        <TabsList className="bg-secondary border border-border text-muted-foreground w-full justify-start h-12">
          <TabsTrigger value="story" className="data-[state=active]:bg-background flex items-center gap-1.5">
            <UserCircle className="w-4 h-4" />
            Story
          </TabsTrigger>
          <TabsTrigger value="timeline" className="data-[state=active]:bg-background flex items-center gap-1.5">
            <Clock className="w-4 h-4" />
            Timeline
          </TabsTrigger>
          <TabsTrigger value="graph" className="data-[state=active]:bg-background flex items-center gap-1.5">
            <Network className="w-4 h-4" />
            Graph
          </TabsTrigger>
          <TabsTrigger value="fhir" className="data-[state=active]:bg-background flex items-center gap-1.5">
            <Code2 className="w-4 h-4" />
            FHIR
          </TabsTrigger>
        </TabsList>

        {/* ═══════════════════════════════════════════════════════════════
            TAB 1: STORY — Patient overview with domain summary cards
            ═══════════════════════════════════════════════════════════════ */}
        <TabsContent value="story" className="mt-6 space-y-6">
          {/* Domain count cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {domainCards.map(({ label, count, icon: Icon, color, bg }) => (
              <Card key={label} className={`border ${bg} shadow-sm hover:opacity-90 transition-opacity cursor-default`}>
                <CardContent className="p-4 flex items-center gap-3">
                  <Icon className={`w-5 h-5 ${color} shrink-0`} />
                  <div>
                    <div className={`text-xl font-bold ${color}`}>{count}</div>
                    <div className="text-xs text-muted-foreground">{label}</div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Demographics + Clinical Overview */}
          <div className="grid md:grid-cols-3 gap-4">
            <Card className="bg-card/50 border-border shadow-sm md:col-span-1">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Demographics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div>
                  <div className="text-muted-foreground mb-1">Full Name</div>
                  <div className="font-medium text-foreground">{p.name}</div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Administrative Gender</div>
                  <div className="font-medium text-foreground capitalize">{p.gender}</div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Birth Date</div>
                  <div className="font-medium text-foreground">{p.birthDate}</div>
                </div>
                <div>
                  <div className="text-muted-foreground mb-1">Patient ID</div>
                  <div className="font-medium text-foreground font-mono text-xs">{cleanId}</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card/50 border-border shadow-sm md:col-span-2">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Clinical Overview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {/* Recorded Conditions */}
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3 flex items-center"><Activity className="w-4 h-4 mr-2"/> Recorded Conditions</h4>
                    <div className="flex gap-2 flex-wrap">
                      {p.conditions?.length ? p.conditions.slice(0, 5).map((c: any) => (
                        <Badge key={c.id} variant="secondary" className="bg-rose-100/50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:text-rose-400 dark:border-rose-500/20 transition-colors">
                          {c.display_name || c.code}
                        </Badge>
                      )) : <span className="text-muted-foreground text-sm">No recorded conditions</span>}
                    </div>
                  </div>

                  {/* Recorded Medication Requests */}
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3 flex items-center"><Pill className="w-4 h-4 mr-2"/> Recorded Medication Requests</h4>
                    <div className="flex gap-2 flex-wrap">
                      {p.medications?.length ? p.medications.slice(0, 4).map((m: any) => (
                        <Badge key={m.id} variant="secondary" className="bg-purple-100/50 text-purple-700 border-purple-200 dark:bg-purple-500/10 dark:text-purple-400 dark:border-purple-500/20 transition-colors">
                          {m.display_name || m.code}
                        </Badge>
                      )) : <span className="text-muted-foreground text-sm">No recorded medications</span>}
                    </div>
                  </div>

                  {/* Recent Encounters */}
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3 flex items-center"><Calendar className="w-4 h-4 mr-2"/> Recent Encounters</h4>
                    <div className="flex gap-2 flex-wrap">
                      {p.encounters?.length ? p.encounters.slice(0, 4).map((e: any) => (
                        <Badge key={e.id} variant="secondary" className="bg-blue-100/50 text-blue-700 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 dark:border-blue-500/20 transition-colors">
                          {e.start?.split('T')[0] || e.id} ({e.class_code || 'AMB'})
                        </Badge>
                      )) : <span className="text-muted-foreground text-sm">No recorded encounters</span>}
                    </div>
                  </div>

                  {/* Recent Observations */}
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3 flex items-center"><Stethoscope className="w-4 h-4 mr-2"/> Recent Lab Results</h4>
                    <div className="flex gap-2 flex-wrap">
                      {p.observations?.length ? p.observations.slice(0, 4).map((o: any) => (
                        <Badge key={o.id} variant="secondary" className="bg-emerald-100/50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/20 transition-colors">
                          {o.display_name || o.code}: {o.value ?? '—'} {o.unit || ''}
                        </Badge>
                      )) : <span className="text-muted-foreground text-sm">No recorded observations</span>}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Expandable detail tables */}
          {p.conditions?.length > 0 && (
            <Card className="bg-card/50 border-border">
              <CardHeader className="pb-3 border-b border-border">
                <CardTitle className="text-sm font-semibold flex items-center"><Activity className="w-4 h-4 mr-2"/> Problem List ({counts.conditions})</CardTitle>
              </CardHeader>
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead>Problem</TableHead>
                    <TableHead>Code (SNOMED)</TableHead>
                    <TableHead>System</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {p.conditions.map((c: any) => (
                    <TableRow key={c.id} className="border-border hover:bg-muted/50">
                      <TableCell className="font-medium text-foreground">{c.display_name || 'Unknown'}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{c.code}</TableCell>
                      <TableCell className="text-muted-foreground text-sm truncate max-w-xs">{c.system}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}

          {p.encounters?.length > 0 && (
            <Card className="bg-card/50 border-border">
              <CardHeader className="pb-3 border-b border-border">
                <CardTitle className="text-sm font-semibold flex items-center"><Calendar className="w-4 h-4 mr-2"/> Encounters ({counts.encounters})</CardTitle>
              </CardHeader>
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow className="border-border hover:bg-transparent">
                    <TableHead className="w-[120px]">Date</TableHead>
                    <TableHead>Class</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {p.encounters.map((e: any) => (
                    <TableRow key={e.id} className="border-border hover:bg-muted/50">
                      <TableCell className="font-medium">{e.start?.split('T')[0] || 'Unknown'}</TableCell>
                      <TableCell><Badge variant="outline" className="bg-background">{e.class_code || 'AMB'}</Badge></TableCell>
                      <TableCell><Badge variant="secondary" className="bg-secondary">{e.status}</Badge></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
        </TabsContent>

        {/* ═══════════════════════════════════════════════════════════════
            TAB 2: TIMELINE — Chronological clinical journey
            ═══════════════════════════════════════════════════════════════ */}
        <TabsContent value="timeline" className="mt-6">
          <Card className="bg-card/50 border-border p-6">
            <Suspense fallback={<div className="h-64 animate-pulse bg-muted rounded-md" />}>
              <TimelineView patientId={cleanId} />
            </Suspense>
          </Card>
        </TabsContent>

        {/* ═══════════════════════════════════════════════════════════════
            TAB 3: GRAPH — Interactive knowledge graph with inspector
            ═══════════════════════════════════════════════════════════════ */}
        <TabsContent value="graph" className="mt-6">
          <div className="h-[650px]">
            <Suspense fallback={<div className="h-full animate-pulse bg-muted rounded-md" />}>
              <PatientGraphTab patientId={cleanId} />
            </Suspense>
          </div>
        </TabsContent>

        {/* ═══════════════════════════════════════════════════════════════
            TAB 4: FHIR — Raw resource data
            ═══════════════════════════════════════════════════════════════ */}
        <TabsContent value="fhir" className="mt-6">
          <Card className="bg-card/50 border-border">
            <CardHeader className="pb-3 border-b border-border">
              <CardTitle className="text-sm font-semibold flex items-center">
                <Code2 className="w-4 h-4 mr-2"/> Raw FHIR Data
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {fhirResource ? (
                <pre className="text-xs text-muted-foreground font-mono p-4 overflow-x-auto max-h-[600px] overflow-y-auto">
                  {JSON.stringify(fhirResource, null, 2)}
                </pre>
              ) : (
                <p role="alert" className="p-4 text-sm text-muted-foreground">The Patient FHIR source is unavailable. Refresh this page to try again.</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
