"""Transformer from FHIR models to Graph canonical models."""

import re
from typing import Any

from libs.fhir.models.base import FHIRResource
from libs.fhir.references import ReferenceIndex
from libs.graph.schema import GraphEdge, GraphNode

camel_pattern1 = re.compile(r"(.)([A-Z][a-z]+)")
camel_pattern2 = re.compile(r"([a-z0-9])([A-Z])")
_FHIR_ID = re.compile(r"[A-Za-z0-9.-]{1,64}")
_LOCAL_REFERENCE = re.compile(r"[A-Za-z][A-Za-z0-9]*/[A-Za-z0-9.-]{1,64}")
_RELATIONSHIP_TYPE = re.compile(r"[A-Z_][A-Z0-9_]*")


def split_camel(text: str) -> str:
    new_text = camel_pattern1.sub(r"\1_\2", text.strip())
    new_text = camel_pattern2.sub(r"\1_\2", new_text.strip())
    return new_text.lower().strip()


def flatten_fhir(nested_json: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def flatten(json_to_flatten: Any, name: str = "") -> None:
        if name == "text_":
            return
        elif isinstance(json_to_flatten, dict):
            for sub_attribute in json_to_flatten:
                flatten(json_to_flatten[sub_attribute], name + split_camel(sub_attribute) + "_")
        elif isinstance(json_to_flatten, list):
            for i, sub_json in enumerate(json_to_flatten):
                flatten(sub_json, name + str(i) + "_")
        else:
            attrib_name = name[:-1]
            out[attrib_name] = json_to_flatten

    flatten(nested_json)
    return out


class FHIRToGraphTransformer:
    """Transforms FHIR resources into a dynamically flattened Graph structure."""

    def transform(
        self,
        resource: FHIRResource,
        *,
        source: dict[str, Any] | None = None,
        reference_index: ReferenceIndex | None = None,
        bundle_scope: str | None = None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Transform a validated resource, preserving original serialized fields when supplied.

        The local FHIR models cover a subset of R4. Transforming the original JSON
        retains additional clinical fields and references those models do not declare.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        res_dict = source if source is not None else resource.to_dict()
        res_type = resource.resourceType
        if _FHIR_ID.fullmatch(resource.id) is None:
            raise ValueError(f"Invalid FHIR resource ID: {resource.id!r}")
        res_id = f"{res_type}/{resource.id}"

        # 1. Flatten all properties
        flat_props = flatten_fhir(res_dict)
        flat_props["id"] = res_id  # Ensure canonical ID is present

        # Stringify dates for Neo4j compatibility
        for k, v in flat_props.items():
            if hasattr(v, "isoformat"):
                flat_props[k] = v.isoformat()

        # 2. Extract standard references dynamically
        def extract_references(data: Any, path: str = "", json_path: str = "") -> None:
            if isinstance(data, dict):
                if "reference" in data:
                    ref = data["reference"]
                    target = ref
                    if reference_index is not None and isinstance(ref, str):
                        resolution = reference_index.resolve(
                            ref, res_dict, bundle_scope=bundle_scope, path=f"{json_path}.reference"
                        )
                        if resolution.status == "contained":
                            target = None
                        elif resolution.status == "resolved":
                            target = resolution.target_key
                            flat_props[f"{path}_reference_canonical"] = target
                        else:
                            raise ValueError(
                                f"Unsupported FHIR reference at {json_path}: {ref!r}; {resolution.diagnostic}"
                            )
                    elif not isinstance(ref, str) or _LOCAL_REFERENCE.fullmatch(ref) is None:
                        raise ValueError(
                            f"Unsupported FHIR reference at {path or '<root>'}: {ref!r}; "
                            "expected a local ResourceType/id reference"
                        )
                    # Determine relationship name from path (e.g. "subject" -> "SUBJECT")
                    rel_type = "REFERENCES"
                    if path:
                        parts = [p for p in path.split("_") if p and not p.isdigit()]
                        if parts:
                            rel_type = parts[-1].upper()
                    if _RELATIONSHIP_TYPE.fullmatch(rel_type) is None:
                        raise ValueError(f"Invalid FHIR reference field path: {path!r}")

                    if target is not None and not json_path.startswith("contained["):
                        edges.append(GraphEdge(source_id=res_id, target_id=target, type=rel_type))

                for k, v in data.items():
                    extract_references(
                        v,
                        path + "_" + split_camel(k) if path else split_camel(k),
                        f"{json_path}.{k}" if json_path else k,
                    )
            elif isinstance(data, list):
                for index, v in enumerate(data):
                    extract_references(v, f"{path}_{index}", f"{json_path}[{index}]")

        extract_references(res_dict)
        nodes.append(GraphNode(id=res_id, labels=[res_type], properties=flat_props))

        return nodes, edges
