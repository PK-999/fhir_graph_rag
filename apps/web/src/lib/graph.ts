export function getNodeDisplayName(id: string, properties: Record<string, unknown>): string {
  const givenNames = Object.keys(properties)
    .filter((key) => /^name_0_given_\d+$/.test(key))
    .sort((a, b) => Number(a.split("_").at(-1)) - Number(b.split("_").at(-1)))
    .map((key) => properties[key]);
  const patientName = [...givenNames, properties.name_0_family]
    .filter((value) => typeof value === "string" && value.trim())
    .join(" ");

  const candidates = [
    properties.display_name,
    properties.name,
    properties.name_0_text,
    patientName,
    properties.code_text,
    properties.code_coding_0_display,
    properties.medication_codeable_concept_text,
    properties.medication_codeable_concept_coding_0_display,
    properties.medication_reference_display,
    properties.code,
    properties.code_coding_0_code,
    properties.medication_codeable_concept_coding_0_code,
  ];
  const display = candidates.find((value) => typeof value === "string" && value.trim());
  return typeof display === "string" ? display.trim() : id.split("/").slice(1).join("/") || id;
}

export interface GraphEdgeIdentity {
  id?: string;
  source: string;
  target: string;
  type: string;
}

export function getGraphEdgeId(edge: GraphEdgeIdentity): string {
  return edge.id || `edge:${JSON.stringify([edge.source, edge.type, edge.target])}`;
}
