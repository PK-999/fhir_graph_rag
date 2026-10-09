import { Handle, Position } from "@xyflow/react";
import { Activity, Pill, User, FileText, Calendar, Crosshair, AlertTriangle } from "lucide-react";

export function ClinicalNode({ data }: { data: any }) {
  const type = data.type || "Unknown";
  
  // Icon and Color mapping based on FHIR resource type
  let Icon = FileText;
  let bgClass = "bg-slate-100 dark:bg-slate-800";
  let borderClass = "border-slate-300 dark:border-slate-600";
  let textClass = "text-slate-800 dark:text-slate-200";

  switch (type) {
    case "Patient":
      Icon = User;
      bgClass = "bg-emerald-50 dark:bg-emerald-950/30";
      borderClass = "border-emerald-500";
      textClass = "text-emerald-700 dark:text-emerald-400";
      break;
    case "Encounter":
      Icon = Calendar;
      bgClass = "bg-blue-50 dark:bg-blue-950/30";
      borderClass = "border-blue-500";
      textClass = "text-blue-700 dark:text-blue-400";
      break;
    case "Condition":
      Icon = AlertTriangle;
      bgClass = "bg-rose-50 dark:bg-rose-950/30";
      borderClass = "border-rose-500";
      textClass = "text-rose-700 dark:text-rose-400";
      break;
    case "MedicationRequest":
    case "Medication":
      Icon = Pill;
      bgClass = "bg-indigo-50 dark:bg-indigo-950/30";
      borderClass = "border-indigo-500";
      textClass = "text-indigo-700 dark:text-indigo-400";
      break;
    case "Observation":
      Icon = Activity;
      bgClass = "bg-cyan-50 dark:bg-cyan-950/30";
      borderClass = "border-cyan-500";
      textClass = "text-cyan-700 dark:text-cyan-400";
      break;
    case "Procedure":
      Icon = Crosshair;
      bgClass = "bg-orange-50 dark:bg-orange-950/30";
      borderClass = "border-orange-500";
      textClass = "text-orange-700 dark:text-orange-400";
      break;
  }

  return (
    <div className={`shadow-sm rounded-xl border-2 ${borderClass} ${bgClass} overflow-hidden w-64 transition-all hover:shadow-md`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 border-2 bg-white" />
      <div className={`px-3 py-2 flex items-center gap-2 border-b ${borderClass} bg-white/50 dark:bg-black/20`}>
        <Icon className={`w-4 h-4 ${textClass}`} />
        <span className={`text-xs font-bold uppercase tracking-wider ${textClass}`}>{type}</span>
      </div>
      <div className="p-3">
        <h3 className="text-sm font-semibold text-foreground line-clamp-2" title={data.label}>
          {data.label}
        </h3>
        {/* Render a few key properties to simulate semantic zoom */}
        <div className="mt-2 text-xs text-muted-foreground flex flex-col gap-1">
          {Object.entries(data)
            .filter(([k, v]) => !["id", "label", "type", "description"].includes(k) && typeof v === "string")
            .slice(0, 2)
            .map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="opacity-70 capitalize">{k.replace(/_/g, ' ')}</span>
                <span className="font-medium truncate max-w-[120px]" title={v as string}>{v as string}</span>
              </div>
          ))}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 border-2 bg-white" />
    </div>
  );
}
