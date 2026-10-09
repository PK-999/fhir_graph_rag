import { useEffect, useState } from "react";
import { User, Activity, Pill, Calendar, Stethoscope } from "lucide-react";

export type ViewMode = "patient-360" | "clinical-journey" | "explorer";

interface PatientSidebarProps {
  patientId: string;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onStorySelect: (story: string) => void;
}

export function PatientSidebar({ patientId, viewMode, onViewModeChange, onStorySelect }: PatientSidebarProps) {
  const [patient, setPatient] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";
        const res = await fetch(`${url}/patients/${patientId}`);
        if (res.ok) {
          const data = await res.json();
          setPatient(data);
        }
      } catch (err) {
        console.error("Failed to load patient", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [patientId]);

  if (loading) {
    return <div className="w-64 border-r border-border bg-card p-4 flex flex-col gap-4 animate-pulse">
      <div className="h-16 bg-muted rounded-xl"></div>
      <div className="h-8 bg-muted rounded-xl mt-4"></div>
      <div className="h-8 bg-muted rounded-xl"></div>
      <div className="h-8 bg-muted rounded-xl"></div>
    </div>;
  }

  if (!patient) return null;

  return (
    <div className="w-72 border-r border-border bg-card flex flex-col overflow-y-auto shrink-0">
      {/* Patient Identity */}
      <div className="p-6 border-b border-border/50">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center text-emerald-700 dark:text-emerald-400">
            <User className="w-6 h-6" />
          </div>
          <div>
            <h2 className="font-semibold text-lg leading-tight truncate" title={patient.name}>{patient.name}</h2>
            <p className="text-sm text-muted-foreground">{patient.gender} · {patient.birthDate}</p>
          </div>
        </div>

        {/* Resource Counts */}
        <div className="grid grid-cols-2 gap-3 mt-6">
          <div className="bg-muted/50 p-3 rounded-xl border border-border/50 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
              <Activity className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Conditions</span>
            </div>
            <span className="text-xl font-semibold">{patient.counts?.conditions || 0}</span>
          </div>
          <div className="bg-muted/50 p-3 rounded-xl border border-border/50 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-indigo-600 dark:text-indigo-400">
              <Pill className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Medications</span>
            </div>
            <span className="text-xl font-semibold">{patient.counts?.medications || 0}</span>
          </div>
          <div className="bg-muted/50 p-3 rounded-xl border border-border/50 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-blue-600 dark:text-blue-400">
              <Calendar className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Encounters</span>
            </div>
            <span className="text-xl font-semibold">{patient.counts?.encounters || 0}</span>
          </div>
          <div className="bg-muted/50 p-3 rounded-xl border border-border/50 flex flex-col gap-1">
            <div className="flex items-center gap-1.5 text-teal-600 dark:text-teal-400">
              <Stethoscope className="w-3.5 h-3.5" />
              <span className="text-xs font-medium uppercase tracking-wider">Observations</span>
            </div>
            <span className="text-xl font-semibold">{patient.counts?.observations || 0}</span>
          </div>
        </div>
      </div>

      {/* View Modes */}
      <div className="p-4 border-b border-border/50">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Visualization Mode</h3>
        <div className="flex flex-col gap-2">
          <button 
            onClick={() => onViewModeChange("patient-360")}
            className={`px-3 py-2 text-sm text-left rounded-md transition-colors ${viewMode === "patient-360" ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted text-foreground"}`}
          >
            Patient 360 Graph
          </button>
          <button 
            onClick={() => onViewModeChange("clinical-journey")}
            className={`px-3 py-2 text-sm text-left rounded-md transition-colors ${viewMode === "clinical-journey" ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted text-foreground"}`}
          >
            Clinical Journey
          </button>
          <button 
            onClick={() => onViewModeChange("explorer")}
            className={`px-3 py-2 text-sm text-left rounded-md transition-colors ${viewMode === "explorer" ? "bg-primary text-primary-foreground font-medium" : "hover:bg-muted text-foreground"}`}
          >
            Developer Explorer
          </button>
        </div>
      </div>

      {/* Story Mode */}
      <div className="p-4">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Highlight Resource Types</h3>
        <div className="flex flex-col gap-1.5">
          {["Patient Overview", "Conditions and Labs", "Encounters and Procedures", "Medication History"].map((story) => (
            <button 
              key={story}
              onClick={() => onStorySelect(story)}
              className="px-3 py-1.5 text-sm text-left rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-border border border-muted-foreground/30"></div>
              {story}
            </button>
          ))}
        </div>
      </div>

    </div>
  );
}
