"""Transformer from FHIR models to Graph canonical models."""

import re
from typing import Any

from libs.fhir.models.base import FHIRResource
from libs.graph.schema import GraphEdge, GraphNode


camel_pattern1 = re.compile(r'(.)([A-Z][a-z]+)')
camel_pattern2 = re.compile(r'([a-z0-9])([A-Z])')

def split_camel(text: str) -> str:
    new_text = camel_pattern1.sub(r'\1_\2', text.strip())
    new_text = camel_pattern2.sub(r'\1_\2', new_text.strip())
    return new_text.lower().strip()

def flatten_fhir(nested_json: dict) -> dict:
    out = {}

    def flatten(json_to_flatten, name=''):
        if name == 'text_':
            return
        elif isinstance(json_to_flatten, dict):
            for sub_attribute in json_to_flatten:
                flatten(json_to_flatten[sub_attribute], name + split_camel(sub_attribute) + '_')
        elif isinstance(json_to_flatten, list):
            for i, sub_json in enumerate(json_to_flatten):
                flatten(sub_json, name + str(i) + '_')
        else:
            attrib_name = name[:-1]
            out[attrib_name] = json_to_flatten

    flatten(nested_json)
    return out


class FHIRToGraphTransformer:
    """Transforms FHIR resources into a dynamically flattened Graph structure."""

    def transform(self, resource: FHIRResource) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Transform a single FHIR resource."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        res_dict = resource.model_dump(exclude_none=True)
        res_type = resource.resourceType
        res_id = f"{res_type}/{resource.id}"

        # 1. Flatten all properties
        flat_props = flatten_fhir(res_dict)
        flat_props["id"] = res_id  # Ensure canonical ID is present

        # Stringify dates for Neo4j compatibility
        for k, v in flat_props.items():
            if hasattr(v, "isoformat"):
                flat_props[k] = v.isoformat()

        primary_node = GraphNode(id=res_id, labels=[res_type], properties=flat_props)
        nodes.append(primary_node)

        # 2. Extract standard references dynamically
        def extract_references(data, path=""):
            if isinstance(data, dict):
                if "reference" in data and isinstance(data["reference"], str) and "/" in data["reference"]:
                    ref = data["reference"]
                    # Determine relationship name from path (e.g. "subject" -> "SUBJECT")
                    rel_type = "REFERENCES"
                    if path:
                        parts = [p for p in path.split("_") if p and not p.isdigit()]
                        if parts:
                            rel_type = parts[-1].upper()
                    
                    edges.append(GraphEdge(source_id=res_id, target_id=ref, type=rel_type))
                
                for k, v in data.items():
                    extract_references(v, path + "_" + split_camel(k) if path else split_camel(k))
            elif isinstance(data, list):
                for v in data:
                    extract_references(v, path)

        extract_references(res_dict)

        return nodes, edges
