"""
BPMN Parser — Extrai elementos de XML BPMN 2.0 e constrói grafo NetworkX.
==========================================================================
Suporta arquivos exportados pelo Bizagi (.bpmn / .xpdl).
Produz um BpmnModel com todos os elementos, metadados visuais e grafo dirigido.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import networkx as nx

# ── Namespaces BPMN 2.0 ────────────────────────────────────────────
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

NS = {
    "bpmn": BPMN_NS,
    "bpmndi": BPMNDI_NS,
    "dc": DC_NS,
    "di": DI_NS,
}


# ── Data Classes ────────────────────────────────────────────────────
@dataclass
class BpmnBounds:
    """Position and size of a visual element."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class BpmnWaypoint:
    x: float = 0.0
    y: float = 0.0


@dataclass
class BpmnElement:
    """Generic BPMN element."""
    id: str = ""
    name: str = ""
    tag: str = ""           # local tag name (e.g., "task", "startEvent")
    element_type: str = ""  # classified: task/event/gateway/data/annotation
    bounds: Optional[BpmnBounds] = None
    lane_id: str = ""
    lane_name: str = ""
    # For events
    event_subtype: str = ""  # start/end/intermediate/boundary, throw/catch, link/timer/etc.
    is_boundary: bool = False
    attached_to: str = ""
    # For gateways
    gateway_type: str = ""  # exclusive/parallel/inclusive/eventBased
    # Font info from BPMNDI
    font_name: str = ""
    font_size: float = 0.0
    font_bold: bool = False
    font_italic: bool = False


@dataclass
class BpmnFlow:
    """Sequence flow between two elements."""
    id: str = ""
    name: str = ""
    source_ref: str = ""
    target_ref: str = ""
    waypoints: list = field(default_factory=list)  # List[BpmnWaypoint]


@dataclass
class BpmnLane:
    """Lane within a pool."""
    id: str = ""
    name: str = ""
    y_position: float = 0.0  # For ordering top→bottom
    element_refs: list = field(default_factory=list)


@dataclass
class BpmnPool:
    """Participant / Pool."""
    id: str = ""
    name: str = ""
    process_ref: str = ""


@dataclass
class BpmnAssociation:
    """Association between annotation and element."""
    id: str = ""
    source_ref: str = ""
    target_ref: str = ""


@dataclass
class BpmnDataObject:
    """Data Object or Data Store Reference."""
    id: str = ""
    name: str = ""
    data_type: str = ""  # "dataObject" or "dataStore"
    bounds: Optional[BpmnBounds] = None


@dataclass
class BpmnHeader:
    """Parsed header from the first TextAnnotation."""
    title: str = ""
    author: str = ""
    version: str = ""
    description: str = ""
    raw_text: str = ""
    annotation_id: str = ""


@dataclass
class BpmnModel:
    """Complete parsed BPMN model."""
    # Core elements
    elements: dict = field(default_factory=dict)       # id → BpmnElement
    flows: dict = field(default_factory=dict)           # id → BpmnFlow
    lanes: list = field(default_factory=list)            # List[BpmnLane]
    pools: list = field(default_factory=list)            # List[BpmnPool]
    associations: list = field(default_factory=list)     # List[BpmnAssociation]
    data_objects: dict = field(default_factory=dict)     # id → BpmnDataObject
    annotations: dict = field(default_factory=dict)      # id → BpmnElement (textAnnotation)

    # Metadata
    header: Optional[BpmnHeader] = None
    process_id: str = ""
    process_name: str = ""

    # Graph
    graph: Optional[nx.DiGraph] = None

    # Visual bounds map: element_id → BpmnBounds
    bounds_map: dict = field(default_factory=dict)

    # Edge waypoints: flow_id → List[BpmnWaypoint]
    edge_waypoints: dict = field(default_factory=dict)

    # Font styles from BPMNDI (element_id → dict with font info)
    font_styles: dict = field(default_factory=dict)


# ── Element Classification ──────────────────────────────────────────

# BPMN event tags
EVENT_TAGS = {
    "startEvent", "endEvent", "intermediateThrowEvent",
    "intermediateCatchEvent", "boundaryEvent",
}

# BPMN gateway tags
GATEWAY_TAGS = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
}

# BPMN task/activity tags
TASK_TAGS = {
    "task", "userTask", "serviceTask", "scriptTask", "sendTask",
    "receiveTask", "manualTask", "businessRuleTask", "subProcess",
    "callActivity",
}

DATA_TAGS = {
    "dataObjectReference", "dataStoreReference", "dataObject",
}


def _local_tag(full_tag: str) -> str:
    """Extract local tag name from namespaced tag."""
    if "}" in full_tag:
        return full_tag.split("}")[-1]
    return full_tag


def _classify_element(tag: str) -> str:
    """Classify element by its local tag name."""
    if tag in EVENT_TAGS:
        return "event"
    if tag in GATEWAY_TAGS:
        return "gateway"
    if tag in TASK_TAGS:
        return "task"
    if tag in DATA_TAGS:
        return "data"
    if tag == "textAnnotation":
        return "annotation"
    return "other"


def _classify_event(tag: str, elem) -> str:
    """Get event subtype details."""
    parts = []
    # Base type
    if "start" in tag.lower():
        parts.append("start")
    elif "end" in tag.lower():
        parts.append("end")
    elif "boundary" in tag.lower():
        parts.append("boundary")
    elif "intermediate" in tag.lower():
        if "Throw" in tag:
            parts.append("intermediate_throw")
        elif "Catch" in tag:
            parts.append("intermediate_catch")
        else:
            parts.append("intermediate")

    # Check for link event definition
    for child in elem:
        child_tag = _local_tag(child.tag)
        if "linkEventDefinition" in child_tag:
            parts.append("link")
        elif "timerEventDefinition" in child_tag:
            parts.append("timer")
        elif "messageEventDefinition" in child_tag:
            parts.append("message")
        elif "signalEventDefinition" in child_tag:
            parts.append("signal")
        elif "errorEventDefinition" in child_tag:
            parts.append("error")
        elif "escalationEventDefinition" in child_tag:
            parts.append("escalation")

    return "_".join(parts) if parts else tag


def _classify_gateway(tag: str) -> str:
    """Get gateway type."""
    if "exclusive" in tag.lower():
        return "exclusive"
    if "parallel" in tag.lower():
        return "parallel"
    if "inclusive" in tag.lower():
        return "inclusive"
    if "eventBased" in tag.lower():
        return "eventBased"
    if "complex" in tag.lower():
        return "complex"
    return "unknown"


# ── Header Parsing ──────────────────────────────────────────────────

def _parse_header(text: str, annotation_id: str) -> BpmnHeader:
    """Parse structured header from TextAnnotation text."""
    header = BpmnHeader(raw_text=text, annotation_id=annotation_id)

    # Try to extract fields by keyword
    lines = text.strip().split("\n")

    for line in lines:
        line_stripped = line.strip()
        lower = line_stripped.lower()

        if lower.startswith("título:") or lower.startswith("titulo:"):
            header.title = line_stripped.split(":", 1)[1].strip()
        elif lower.startswith("autor:"):
            header.author = line_stripped.split(":", 1)[1].strip()
        elif lower.startswith("versão:") or lower.startswith("versao:"):
            header.version = line_stripped.split(":", 1)[1].strip()
        elif lower.startswith("descrição:") or lower.startswith("descricao:") or lower.startswith("descriçao:"):
            header.description = line_stripped.split(":", 1)[1].strip()

    # If title not found, first non-empty line might be the title
    if not header.title and lines:
        first_line = lines[0].strip()
        if not any(first_line.lower().startswith(k) for k in
                   ["autor:", "versão:", "versao:", "descrição:", "descricao:"]):
            header.title = first_line

    return header


# ── Main Parser ─────────────────────────────────────────────────────

def parse_bpmn(xml_content: str) -> BpmnModel:
    """
    Parse a BPMN 2.0 XML string into a BpmnModel.

    Returns a fully populated BpmnModel with elements, flows,
    lanes, pools, associations, data objects, header, and NetworkX graph.
    """
    model = BpmnModel()

    # Register namespaces
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"Erro ao parsear XML BPMN: {e}")

    # ── 1. Extract Collaboration (Pools/Participants) ───────────
    collaboration = root.find(f".//{{{BPMN_NS}}}collaboration")
    if collaboration is not None:
        for participant in collaboration.findall(f"{{{BPMN_NS}}}participant"):
            pool = BpmnPool(
                id=participant.get("id", ""),
                name=participant.get("name", ""),
                process_ref=participant.get("processRef", ""),
            )
            model.pools.append(pool)

    # ── 2. Extract Process ──────────────────────────────────────
    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        raise ValueError("Nenhum <bpmn:process> encontrado no XML")

    model.process_id = process.get("id", "")
    model.process_name = process.get("name", "")

    # ── 3. Extract Lanes ────────────────────────────────────────
    lane_set = process.find(f"{{{BPMN_NS}}}laneSet")
    element_to_lane = {}

    if lane_set is not None:
        for lane_elem in lane_set.findall(f"{{{BPMN_NS}}}lane"):
            lane_id = lane_elem.get("id", "")
            lane_name = lane_elem.get("name", "")
            refs = []
            for ref in lane_elem.findall(f"{{{BPMN_NS}}}flowNodeRef"):
                if ref.text:
                    refs.append(ref.text)
                    element_to_lane[ref.text] = (lane_id, lane_name)

            lane = BpmnLane(id=lane_id, name=lane_name, element_refs=refs)
            model.lanes.append(lane)

    # ── 4. Extract Flow Elements ────────────────────────────────
    first_annotation = None

    for child in process:
        tag = _local_tag(child.tag)
        elem_id = child.get("id", "")
        elem_name = child.get("name", "")

        if not elem_id:
            continue

        # Sequence Flows
        if tag == "sequenceFlow":
            flow = BpmnFlow(
                id=elem_id,
                name=elem_name,
                source_ref=child.get("sourceRef", ""),
                target_ref=child.get("targetRef", ""),
            )
            model.flows[elem_id] = flow
            continue

        # Lane Set already processed
        if tag == "laneSet":
            continue

        # Documentation
        if tag == "documentation":
            continue

        # Data Objects / Data Stores
        if tag in DATA_TAGS:
            data_obj = BpmnDataObject(
                id=elem_id,
                name=elem_name,
                data_type="dataStore" if "Store" in tag else "dataObject",
            )
            model.data_objects[elem_id] = data_obj
            continue

        # Text Annotations
        if tag == "textAnnotation":
            text_content = ""
            text_elem = child.find(f"{{{BPMN_NS}}}text")
            if text_elem is not None and text_elem.text:
                text_content = text_elem.text

            annotation = BpmnElement(
                id=elem_id,
                name=text_content,
                tag=tag,
                element_type="annotation",
            )
            model.annotations[elem_id] = annotation

            if first_annotation is None:
                first_annotation = (elem_id, text_content)
            continue

        # Associations
        if tag == "association":
            assoc = BpmnAssociation(
                id=elem_id,
                source_ref=child.get("sourceRef", ""),
                target_ref=child.get("targetRef", ""),
            )
            model.associations.append(assoc)
            continue

        # Flow elements (events, tasks, gateways)
        element_type = _classify_element(tag)
        lane_id, lane_name = element_to_lane.get(elem_id, ("", ""))

        element = BpmnElement(
            id=elem_id,
            name=elem_name,
            tag=tag,
            element_type=element_type,
            lane_id=lane_id,
            lane_name=lane_name,
        )

        # Event-specific
        if element_type == "event":
            element.event_subtype = _classify_event(tag, child)
            if tag == "boundaryEvent":
                element.is_boundary = True
                element.attached_to = child.get("attachedToRef", "")

        # Gateway-specific
        if element_type == "gateway":
            element.gateway_type = _classify_gateway(tag)

        model.elements[elem_id] = element

    # ── 5. Also search for annotations/associations at root level ──
    for child in root:
        tag = _local_tag(child.tag)
        if tag == "textAnnotation":
            elem_id = child.get("id", "")
            text_content = ""
            text_elem = child.find(f"{{{BPMN_NS}}}text")
            if text_elem is not None and text_elem.text:
                text_content = text_elem.text
            if elem_id and elem_id not in model.annotations:
                model.annotations[elem_id] = BpmnElement(
                    id=elem_id, name=text_content, tag=tag,
                    element_type="annotation",
                )
                if first_annotation is None:
                    first_annotation = (elem_id, text_content)

        if tag == "association":
            elem_id = child.get("id", "")
            assoc = BpmnAssociation(
                id=elem_id,
                source_ref=child.get("sourceRef", ""),
                target_ref=child.get("targetRef", ""),
            )
            if elem_id:
                model.associations.append(assoc)

    # ── 6. Parse Header from first TextAnnotation ───────────────
    if first_annotation:
        model.header = _parse_header(first_annotation[1], first_annotation[0])

    # ── 7. Extract BPMNDI visual data ───────────────────────────
    diagram = root.find(f".//{{{BPMNDI_NS}}}BPMNDiagram")
    if diagram is not None:
        plane = diagram.find(f"{{{BPMNDI_NS}}}BPMNPlane")
        if plane is not None:
            # Shapes
            for shape in plane.findall(f"{{{BPMNDI_NS}}}BPMNShape"):
                bpmn_element_id = shape.get("bpmnElement", "")
                bounds_elem = shape.find(f"{{{DC_NS}}}Bounds")

                if bounds_elem is not None:
                    bounds = BpmnBounds(
                        x=float(bounds_elem.get("x", 0)),
                        y=float(bounds_elem.get("y", 0)),
                        width=float(bounds_elem.get("width", 0)),
                        height=float(bounds_elem.get("height", 0)),
                    )
                    model.bounds_map[bpmn_element_id] = bounds

                    # Assign bounds to elements
                    if bpmn_element_id in model.elements:
                        model.elements[bpmn_element_id].bounds = bounds
                    if bpmn_element_id in model.data_objects:
                        model.data_objects[bpmn_element_id].bounds = bounds
                    if bpmn_element_id in model.annotations:
                        model.annotations[bpmn_element_id].bounds = bounds

                    # Lane Y position
                    for lane in model.lanes:
                        if lane.id == bpmn_element_id:
                            lane.y_position = bounds.y

                # Font/label style (Bizagi extension)
                label = shape.find(f"{{{BPMNDI_NS}}}BPMNLabel")
                font_info = {}
                if label is not None:
                    style = label.find(f"{{{DC_NS}}}Font")
                    if style is not None:
                        font_info = {
                            "name": style.get("name", ""),
                            "size": float(style.get("size", 0)),
                            "isBold": style.get("isBold", "false").lower() == "true",
                            "isItalic": style.get("isItalic", "false").lower() == "true",
                        }
                # Also check for Bizagi-specific Extension elements
                ext = shape.find(f".//{{{BPMNDI_NS}}}extension")
                if ext is None:
                    # Try generic extension
                    for child_elem in shape:
                        child_tag = _local_tag(child_elem.tag)
                        if "extension" in child_tag.lower():
                            ext = child_elem
                            break

                if font_info:
                    model.font_styles[bpmn_element_id] = font_info
                    if bpmn_element_id in model.elements:
                        model.elements[bpmn_element_id].font_name = font_info.get("name", "")
                        model.elements[bpmn_element_id].font_size = font_info.get("size", 0)
                        model.elements[bpmn_element_id].font_bold = font_info.get("isBold", False)
                        model.elements[bpmn_element_id].font_italic = font_info.get("isItalic", False)

            # Edges (waypoints)
            for edge in plane.findall(f"{{{BPMNDI_NS}}}BPMNEdge"):
                bpmn_element_id = edge.get("bpmnElement", "")
                waypoints = []
                for wp in edge.findall(f"{{{DI_NS}}}waypoint"):
                    waypoints.append(BpmnWaypoint(
                        x=float(wp.get("x", 0)),
                        y=float(wp.get("y", 0)),
                    ))
                model.edge_waypoints[bpmn_element_id] = waypoints

                # Assign to flow
                if bpmn_element_id in model.flows:
                    model.flows[bpmn_element_id].waypoints = waypoints

    # ── 8. Sort Lanes top→bottom ────────────────────────────────
    model.lanes.sort(key=lambda l: l.y_position)

    # ── 9. Build NetworkX Graph ─────────────────────────────────
    G = nx.DiGraph()

    # Add all flow elements as nodes
    for elem_id, elem in model.elements.items():
        G.add_node(elem_id, **{
            "name": elem.name,
            "tag": elem.tag,
            "type": elem.element_type,
            "lane": elem.lane_name,
        })

    # Add sequence flows as edges
    for flow_id, flow in model.flows.items():
        if flow.source_ref and flow.target_ref:
            G.add_edge(flow.source_ref, flow.target_ref, **{
                "flow_id": flow_id,
                "name": flow.name,
            })

    model.graph = G

    return model
