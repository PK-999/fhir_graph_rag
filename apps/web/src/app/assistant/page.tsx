"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Bot, FileJson, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
const examples = ["List five patients", "Find patients with type 2 diabetes", "Find patients whose latest HbA1c is above 8% with active Metformin", "Show history for Patient/p-000001", "Which patients have active Metformin prescriptions?", "Show lab history for Patient/p-000001"];
type Row = Record<string, unknown>;
type Evidence = { type: string; id: string; label: string; patient_id: string; source_url: string; facts: Row };
type Pagination = { offset: number; limit: number; has_more: boolean; next_offset: number | null };
type Claim = { evidence_id: string; field: string; value: unknown };
type Answer = { status: "answered" | "abstained"; answer: string; results: Row[]; result_count: number; evidence: Evidence[]; planner: string; plan?: Row | null; pagination?: Pagination | null; pages_loaded?: number; claims?: Claim[]; summary?: string | null; summary_metadata?: { requested: boolean; status: string; model?: string | null; claim_count: number } };

function valueText(value: unknown): string {
  return value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
}

function patientHref(id: string) { return `/patients/${encodeURIComponent(id.replace(/^Patient\//, ""))}`; }

function EvidenceCard({ evidence }: { evidence: Evidence }) {
  const [source, setSource] = useState<unknown>();
  const [provenance, setProvenance] = useState<unknown>();
  const [provenanceError, setProvenanceError] = useState<string>();
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  async function inspectProvenance() {
    setProvenanceError(undefined); setProvenanceLoading(true);
    try {
      if (!/^[A-Za-z]+\/[A-Za-z0-9.-]+$/.test(evidence.id)) throw new Error("Invalid source reference.");
      const response = await fetch(`${API}/lineage/resources/${evidence.id}`);
      const payload = await response.json();
      if (!response.ok) throw new Error("Provenance is unavailable. Please retry.");
      setProvenance(payload);
    } catch (failure) { setProvenanceError(failure instanceof Error ? failure.message : "Provenance is unavailable."); }
    finally { setProvenanceLoading(false); }
  }
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  async function inspect() {
    setError(undefined); setLoading(true);
    try {
      if (!/^\/resources\/[A-Za-z]+\/[A-Za-z0-9.-]+$/.test(evidence.source_url)) throw new Error("Invalid source reference.");
      const response = await fetch(`${API}${evidence.source_url}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "FHIR source is unavailable.");
      setSource(payload);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "FHIR source is unavailable."); }
    finally { setLoading(false); }
  }
  return <article aria-label={`Evidence ${evidence.id}`} className="rounded-xl border border-border bg-background p-4 space-y-3">
    <div className="flex flex-wrap items-center gap-2"><Badge variant="secondary">{evidence.type}</Badge><strong className="text-sm">{evidence.label}</strong></div>
    <p className="text-xs font-mono text-muted-foreground break-all">{evidence.id}</p>
    <dl className="space-y-1 text-sm">{Object.entries(evidence.facts).map(([path, value]) => <div key={path} className="grid gap-1 sm:grid-cols-2"><dt className="text-muted-foreground break-all">{path}</dt><dd className="font-medium break-all">{valueText(value)}</dd></div>)}</dl>
    <div className="flex flex-wrap items-center gap-4 text-sm"><Link className="text-blue-600 hover:underline" href={patientHref(evidence.patient_id)}>View patient</Link><Button variant="outline" size="sm" disabled={loading} onClick={inspect}><FileJson className="size-3.5" />{loading ? "Loading source…" : error ? "Retry source" : "Inspect FHIR source"}</Button><Button variant="outline" size="sm" disabled={provenanceLoading} onClick={inspectProvenance}>{provenanceLoading ? "Loading provenance…" : provenanceError ? "Retry provenance" : "Inspect provenance"}</Button></div>
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    {provenanceError && <p role="alert" className="text-sm text-red-600">{provenanceError}</p>}
    {provenance !== undefined && <pre role="region" aria-label={`Provenance ${evidence.id}`} className="max-h-80 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(provenance, null, 2)}</pre>}
    {source !== undefined && <pre role="region" aria-label={`FHIR source ${evidence.id}`} className="max-h-80 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(source, null, 2)}</pre>}
  </article>;
}

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [useSummaryModel, setUseSummaryModel] = useState(false);
  const [askedSummary, setAskedSummary] = useState(false);
  const [answer, setAnswer] = useState<Answer>();
  const [asked, setAsked] = useState("");
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string>();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true); setError(undefined); setPageError(undefined); setAnswer(undefined); setAsked(question); setAskedSummary(useSummaryModel);
    try {
      const response = await fetch(`${API}/assistant/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: question, use_summary_model: useSummaryModel }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "The question service failed. Please retry.");
      setAnswer(payload as Answer);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "The question service is unavailable."); }
    finally { setLoading(false); }
  }
  async function loadMore() {
    if (loading || !answer?.plan || !answer.pagination?.has_more || answer.pagination.next_offset === null) return;
    const current = answer;
    setLoading(true); setPageError(undefined);
    try {
      const response = await fetch(`${API}/assistant/query`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: asked, plan: current.plan, offset: current.pagination!.next_offset, use_summary_model: askedSummary }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "More results could not be retrieved. Please retry.");
      if (payload.status !== "answered" || !Array.isArray(payload.results) || !Array.isArray(payload.evidence)) throw new Error("More results could not be retrieved. Please retry.");
      const next = payload as Answer;
      const offset = current.pagination!.next_offset!;
      const limit = current.pagination!.limit;
      const planKeys = Object.keys(current.plan!);
      const identity = current.plan!.intent === "patient_history" ? "resource_id" : current.plan!.intent === "patient_lab_history" ? "observation_id" : "patient_id";
      const seen = new Set(current.results.map(row => row[identity]));
      const uniqueRows = next.results.every(row => {
        const id = row[identity];
        if (typeof id !== "string" || seen.has(id)) return false;
        seen.add(id); return true;
      });
      if (!next.plan || Object.keys(next.plan).length !== planKeys.length || planKeys.some(key => next.plan![key] !== current.plan![key]) ||
          next.pagination?.offset !== offset || next.pagination.limit !== limit || typeof next.pagination.has_more !== "boolean" ||
          next.pagination.next_offset !== (next.pagination.has_more ? offset + limit : null) ||
          next.result_count !== next.results.length || next.results.length === 0 || next.results.length > limit || (next.pagination.has_more && next.results.length !== limit) || !uniqueRows) {
        throw new Error("Continuation page is invalid. Please retry the same page.");
      }
      const evidence = new Map(current.evidence.map(item => [item.id, item]));
      next.evidence.forEach(item => evidence.set(item.id, item));
      const results = [...current.results, ...next.results];
      setAnswer({ ...next, results, result_count: results.length, evidence: [...evidence.values()], pages_loaded: (current.pages_loaded || 1) + 1 });
    } catch (failure) { setPageError(failure instanceof Error ? failure.message : "More results could not be retrieved. Please retry."); }
    finally { setLoading(false); }
  }
  const columns = answer?.results.length ? Object.keys(answer.results[0]).filter(key => !["given", "family", "event_field"].includes(key)) : [];
  return <div className="space-y-6 max-w-6xl mx-auto pb-8">
    <div className="flex items-start gap-3"><div className="rounded-xl bg-blue-500/10 p-3 text-blue-600"><Bot /></div><div><h2 className="text-3xl font-bold tracking-tight">Clinical question explorer</h2><p className="text-muted-foreground mt-1">Retrieve graph facts and inspect the FHIR resources behind them.</p></div></div>
    <p className="rounded-lg bg-amber-500/10 px-4 py-3 text-sm">Synthetic data only. Supports patient lists, condition and medication cohorts, patient and lab history, and latest HbA1c with active Metformin. Answers describe recorded data and do not provide treatment advice.</p>
    <Card><CardHeader><CardTitle>Ask a supported question</CardTitle></CardHeader><CardContent className="space-y-4">
      <div className="flex flex-wrap gap-2">{examples.map(example => <Button key={example} variant="outline" size="sm" className="h-auto py-2 whitespace-normal text-left" disabled={loading} onClick={() => setQuestion(example)}>{example}</Button>)}</div>
      <form onSubmit={submit} className="flex gap-2"><Input aria-label="Question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="Choose an example or enter a supported question" disabled={loading} /><Button type="submit" disabled={loading || !question.trim()} aria-label="Ask question"><Send className="size-4" />{loading ? "Retrieving…" : "Ask"}</Button></form>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useSummaryModel} onChange={event => setUseSummaryModel(event.target.checked)} disabled={loading} />Select cited facts with the local model</label>
      <p className="text-xs text-muted-foreground">Optional. Every selected field and value must match the retrieved evidence. Unavailable or rejected model output leaves retrieval intact.</p>
      {error && <p role="alert" aria-label="Question service error" className="text-red-600 text-sm">{error}</p>}
    </CardContent></Card>
    {answer && <div aria-live="polite" className="space-y-5">
      <Card><CardHeader><CardTitle>{answer.status === "abstained" ? "Unsupported question" : "Retrieved answer"}</CardTitle><p className="text-sm text-muted-foreground">{asked}</p></CardHeader><CardContent className="space-y-3"><p>{(answer.pages_loaded || 1) > 1 && "Latest page: "}{answer.answer}</p>{answer.status === "answered" && <Badge variant="secondary">{answer.result_count} {answer.result_count === 1 ? "result returned" : "results returned"}</Badge>}{(answer.pages_loaded || 1) > 1 && <p className="text-sm text-muted-foreground">Loaded across {answer.pages_loaded} pages.</p>}</CardContent></Card>
      {answer.summary_metadata?.requested && answer.summary_metadata.status !== "validated" && <p className="text-sm text-muted-foreground">Model selection {answer.summary_metadata.status}; retrieved facts remain available.</p>}
      {answer.summary_metadata?.status === "validated" && !!answer.claims?.length && <section role="region" aria-label="Validated model claims" className="rounded-xl border p-4 space-y-2"><h3 className="font-semibold">Cited facts selected by the local model</h3><p className="text-xs text-muted-foreground">Selected from the latest result page. Values were checked against retrieved graph evidence; wording is rendered by the application. Inspect the source to verify the live record.</p><ul className="space-y-2 text-sm">{answer.claims.map((claim, index) => <li key={index}><span className="font-mono">{claim.evidence_id} · {claim.field}</span>: {valueText(claim.value)}</li>)}</ul></section>}
      {answer.status === "answered" && answer.results.length === 0 && <p className="text-muted-foreground">No matching results</p>}
      {answer.results.length > 0 && <div className="overflow-x-auto rounded-xl border"><table aria-label="Retrieved results" className="w-full text-sm"><thead className="bg-muted"><tr>{columns.map(key => <th key={key} className="px-4 py-3 text-left font-medium">{key === "event_at" ? "Recorded time" : key.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{answer.results.map((row, index) => <tr key={index} className="border-t">{columns.map(key => <td key={key} className="px-4 py-3">{key === "patient_id" && typeof row[key] === "string" ? <Link className="text-blue-600 hover:underline" href={patientHref(row[key])}>{row[key]}</Link> : valueText(row[key])}</td>)}</tr>)}</tbody></table></div>}
      {answer.status === "answered" && answer.pagination && <div className="space-y-3">
        {pageError && <p role="alert" aria-label="More results error" className="text-red-600 text-sm">{pageError}</p>}
        {answer.pagination.has_more ? <Button variant="outline" disabled={loading} onClick={loadMore}>{loading ? "Loading more…" : pageError ? "Retry more results" : "Load more results"}</Button> : <p className="text-sm text-muted-foreground">All matching rows have been loaded.</p>}
      </div>}
      {answer.evidence.length > 0 && <section aria-label="FHIR evidence" className="space-y-3"><h3 className="text-xl font-semibold">Source evidence</h3><div className="grid gap-4 lg:grid-cols-2">{answer.evidence.map(evidence => <EvidenceCard key={`${asked}:${evidence.id}`} evidence={evidence} />)}</div></section>}
    </div>}
  </div>;
}
