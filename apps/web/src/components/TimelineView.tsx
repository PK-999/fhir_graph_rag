"use client";

import { useEffect, useState } from "react";
import { Calendar, Activity, Pill, Stethoscope, Scissors, Clock } from "lucide-react";

interface TimelineEvent {
  type: string;
  id: string;
  display_name: string | null;
  code: string | null;
  date: string;
  encounter_id?: string | null;
  status?: string | null;
  value?: number | null;
  unit?: string | null;
}

const TYPE_CONFIG: Record<string, { color: string; bgColor: string; icon: React.ElementType; label: string }> = {
  Encounter:         { color: "text-blue-600 dark:text-blue-400",   bgColor: "bg-blue-50 border-blue-200 dark:bg-blue-500/10 dark:border-blue-500/20",    icon: Calendar,    label: "Encounter" },
  Condition:         { color: "text-rose-600 dark:text-rose-400",    bgColor: "bg-rose-50 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/20",    icon: Activity,    label: "Condition" },
  MedicationRequest: { color: "text-purple-600 dark:text-purple-400",  bgColor: "bg-purple-50 border-purple-200 dark:bg-purple-500/10 dark:border-purple-500/20", icon: Pill,       label: "Medication" },
  Observation:       { color: "text-emerald-600 dark:text-emerald-400", bgColor: "bg-emerald-50 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/20", icon: Stethoscope, label: "Observation" },
  Procedure:         { color: "text-orange-600 dark:text-orange-400",  bgColor: "bg-orange-50 border-orange-200 dark:bg-orange-500/10 dark:border-orange-500/20", icon: Scissors,   label: "Procedure" },
};

function getConfig(type: string) {
  return TYPE_CONFIG[type] || { color: "text-muted-foreground", bgColor: "bg-muted border-border", icon: Clock, label: type };
}

export function TimelineView({ patientId }: { patientId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
        const res = await fetch(`${url}/patients/${patientId}/timeline`);
        const data = await res.json();
        setEvents(data.events || []);
      } catch (err) {
        console.error("Timeline fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [patientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        <div className="animate-pulse">Loading timeline...</div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        No timeline events found.
      </div>
    );
  }

  const filtered = filter ? events.filter(e => e.type === filter) : events;

  // Group events by encounter or keep them floating
  const encountersMap: Record<string, TimelineEvent> = {};
  const eventsByEncounter: Record<string, TimelineEvent[]> = {};
  const floatingEvents: TimelineEvent[] = [];

  // First pass: identify encounters
  for (const ev of events) {
    if (ev.type === "Encounter") {
      encountersMap[ev.id] = ev;
      if (!eventsByEncounter[ev.id]) eventsByEncounter[ev.id] = [];
    }
  }

  // Second pass: attach items
  for (const ev of filtered) {
    if (ev.type === "Encounter") continue; // already handled

    // If we're filtering, and we filter by Encounter, encounters will be empty but maybe we still show filtered children?
    // Actually, if we filter, we just want to see the matched events.
    if (ev.encounter_id && eventsByEncounter[ev.encounter_id]) {
      eventsByEncounter[ev.encounter_id].push(ev);
    } else {
      floatingEvents.push(ev);
    }
  }

  // Build chronologically sorted columns
  // A column is either an Encounter (with its children) or a floating event
  const columns: { date: string; type: "encounter" | "floating"; event: TimelineEvent; children?: TimelineEvent[] }[] = [];

  Object.values(encountersMap).forEach(enc => {
    // If filtering, only show this encounter column if the encounter matches the filter, OR if it has children that match the filter
    const children = eventsByEncounter[enc.id] || [];
    if (!filter || filter === "Encounter" || children.length > 0) {
      columns.push({
        date: enc.date || "",
        type: "encounter",
        event: enc,
        children: children.sort((a, b) => (a.date || "").localeCompare(b.date || "")),
      });
    }
  });

  floatingEvents.forEach(ev => {
    columns.push({
      date: ev.date || "",
      type: "floating",
      event: ev
    });
  });

  columns.sort((a, b) => a.date.localeCompare(b.date));

  const uniqueTypes = [...new Set(events.map(e => e.type))];

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap shrink-0">
        <button
          onClick={() => setFilter(null)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            filter === null
              ? "bg-primary text-primary-foreground border border-primary"
              : "bg-secondary text-secondary-foreground border border-border hover:bg-secondary/80"
          }`}
        >
          All ({events.length})
        </button>
        {uniqueTypes.map(t => {
          const cfg = getConfig(t);
          const count = events.filter(e => e.type === t).length;
          return (
            <button
              key={t}
              onClick={() => setFilter(filter === t ? null : t)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
                filter === t
                  ? `${cfg.bgColor} ${cfg.color} shadow-sm`
                  : "bg-secondary text-secondary-foreground border-border hover:bg-secondary/80"
              }`}
            >
              {cfg.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Horizontal Timeline */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden pb-4">
        <div className="flex gap-6 min-h-full items-stretch px-4 pt-8 border-t-2 border-border mt-4 relative">

          {columns.map((col, idx) => {
            if (col.type === "encounter") {
              const encCfg = getConfig("Encounter");
              const Icon = encCfg.icon;
              return (
                <div key={`col-${idx}`} className="flex flex-col gap-3 min-w-[280px] w-[280px] shrink-0 relative">
                  {/* Timeline node anchor */}
                  <div className="absolute -top-[43px] left-4 w-4 h-4 rounded-full border-2 border-background bg-blue-500 flex items-center justify-center z-10">
                    <div className="w-1.5 h-1.5 rounded-full bg-background" />
                  </div>
                  {/* Date line */}
                  <div className="absolute -top-[24px] left-4 h-6 w-px bg-border" />

                  {/* Encounter Card */}
                  <div className={`rounded-md border px-3 py-2 text-sm ${encCfg.bgColor}`}>
                    <div className="flex items-center gap-2">
                      <Icon className={`w-3.5 h-3.5 ${encCfg.color} shrink-0`} />
                      <span className={`font-medium ${encCfg.color}`}>{encCfg.label}</span>
                      <span className="text-muted-foreground text-xs ml-auto">{col.event.date?.split("T")[0] || ""}</span>
                    </div>
                    <div className="text-foreground mt-0.5 font-medium truncate">
                      {col.event.display_name || col.event.code || col.event.id.split("/")[1]}
                    </div>
                    {col.event.status && (
                      <div className="text-muted-foreground text-xs mt-0.5">Status: {col.event.status}</div>
                    )}
                  </div>

                  {/* Children (Observations, Conditions, etc.) */}
                  {col.children && col.children.length > 0 && (
                    <div className="flex flex-col gap-2 pl-4 border-l-2 border-border/50 ml-4 mt-1">
                      {col.children.map((child, cIdx) => {
                        const childCfg = getConfig(child.type);
                        const ChildIcon = childCfg.icon;
                        return (
                          <div key={`child-${cIdx}`} className={`rounded-md border px-3 py-2 text-xs relative ${childCfg.bgColor}`}>
                            <div className="absolute -left-[18px] top-1/2 -translate-y-1/2 w-4 h-px bg-border/50" />
                            <div className="flex items-center gap-1.5 mb-1">
                              <ChildIcon className={`w-3 h-3 ${childCfg.color} shrink-0`} />
                              <span className={`font-medium ${childCfg.color}`}>{childCfg.label}</span>
                            </div>
                            <div className="text-foreground truncate font-medium">
                              {child.display_name || child.code || child.id.split("/")[1]}
                            </div>
                            {child.value != null && (
                              <div className="text-muted-foreground mt-1">
                                <span className="text-emerald-600 dark:text-emerald-400 font-bold">{child.value}</span>
                                {child.unit && <span className="ml-1">{child.unit}</span>}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            } else {
              // Floating Event
              const ev = col.event;
              const cfg = getConfig(ev.type);
              const Icon = cfg.icon;
              return (
                <div key={`col-${idx}`} className="flex flex-col gap-3 min-w-[240px] w-[240px] shrink-0 relative">
                  {/* Timeline node anchor */}
                  <div className={`absolute -top-[43px] left-4 w-4 h-4 rounded-full border-2 border-background flex items-center justify-center z-10 ${cfg.color.replace("text-", "bg-").replace("dark:text-", "dark:bg-")}`}>
                    <div className="w-1.5 h-1.5 rounded-full bg-background" />
                  </div>
                  {/* Date line */}
                  <div className="absolute -top-[24px] left-4 h-6 w-px bg-border" />

                  <div className={`rounded-md border px-3 py-2 text-sm ${cfg.bgColor}`}>
                    <div className="flex items-center gap-2">
                      <Icon className={`w-3.5 h-3.5 ${cfg.color} shrink-0`} />
                      <span className={`font-medium ${cfg.color}`}>{cfg.label}</span>
                      <span className="text-muted-foreground text-xs ml-auto">{ev.date?.split("T")[0] || ""}</span>
                    </div>
                    <div className="text-foreground mt-0.5 truncate font-medium">
                      {ev.display_name || ev.code || ev.id.split("/")[1]}
                    </div>
                    {ev.value != null && (
                      <div className="text-muted-foreground text-xs mt-1">
                        <span className="text-emerald-600 dark:text-emerald-400 font-bold">{ev.value}</span>
                        {ev.unit && <span className="ml-1">{ev.unit}</span>}
                      </div>
                    )}
                    {ev.status && (
                      <div className="text-muted-foreground text-xs mt-0.5">Status: {ev.status}</div>
                    )}
                  </div>
                </div>
              );
            }
          })}
        </div>
      </div>
    </div>
  );
}
