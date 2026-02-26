"""
BPMN Generator — Validates, wraps, and auto-layouts BPMN XML for Bizagi.
=========================================================================
Includes auto_layout_bpmn() that calculates coordinates for BPMNDiagram
using Python instead of relying on LLM-generated coordinates.
"""

import re
import xml.etree.ElementTree as ET


# Namespace constants
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

# Register namespaces so ET doesn't use ns0, ns1, etc.
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def prepare_bpmn_file(bpmn_xml: str) -> str:
    """
    Takes raw BPMN XML and ensures it is properly formatted
    for import into Bizagi Modeler.
    """
    # Ensure XML declaration
    if not bpmn_xml.strip().startswith("<?xml"):
        bpmn_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + bpmn_xml

    # Ensure required namespaces are present
    required_ns = {
        'xmlns:bpmn': BPMN_NS,
        'xmlns:bpmndi': BPMNDI_NS,
        'xmlns:dc': DC_NS,
        'xmlns:di': DI_NS,
    }

    for ns_prefix, ns_uri in required_ns.items():
        if ns_prefix not in bpmn_xml:
            bpmn_xml = bpmn_xml.replace(
                '<bpmn:definitions',
                f'<bpmn:definitions {ns_prefix}="{ns_uri}"'
            )

    return bpmn_xml


def validate_bpmn_structure(bpmn_xml: str) -> dict:
    """
    Basic structural validation of BPMN XML.
    Returns a dict with 'valid' flag and 'issues' list.
    """
    issues = []

    if '<bpmn:definitions' not in bpmn_xml and '<definitions' not in bpmn_xml:
        issues.append("Missing <bpmn:definitions> root element")

    if '<bpmn:process' not in bpmn_xml and '<process' not in bpmn_xml:
        issues.append("Missing <bpmn:process> element")

    if '<bpmn:startEvent' not in bpmn_xml and '<startEvent' not in bpmn_xml:
        issues.append("Missing start event")

    if '<bpmn:endEvent' not in bpmn_xml and '<endEvent' not in bpmn_xml:
        issues.append("Missing end event")

    has_diagram = '<bpmndi:BPMNDiagram' in bpmn_xml or '<BPMNDiagram' in bpmn_xml
    if not has_diagram:
        issues.append("Missing BPMN diagram information (visual layout)")

    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


# ═══════════════════════════════════════════════════════════════════
# AUTO-LAYOUT: Calcula coordenadas para BPMNDiagram
# ═══════════════════════════════════════════════════════════════════

# Layout constants
LANE_HEIGHT = 150
LANE_PADDING_TOP = 30
POOL_HEADER_WIDTH = 40
ELEMENT_WIDTH = 100
ELEMENT_HEIGHT = 80
EVENT_SIZE = 36
GATEWAY_SIZE = 50
H_GAP = 60  # horizontal gap between elements
V_CENTER_OFFSET = (LANE_HEIGHT - ELEMENT_HEIGHT) // 2

# Element type dimensions
DIMS = {
    "task": (ELEMENT_WIDTH, ELEMENT_HEIGHT),
    "event": (EVENT_SIZE, EVENT_SIZE),
    "gateway": (GATEWAY_SIZE, GATEWAY_SIZE),
}


def _classify_element(tag: str) -> str:
    """Classify a BPMN element by its tag into task/event/gateway."""
    tag_lower = tag.lower()
    if "event" in tag_lower:
        return "event"
    if "gateway" in tag_lower:
        return "gateway"
    return "task"


def auto_layout_bpmn(bpmn_xml: str) -> str:
    """
    Recebe XML BPMN 2.0 SEM seção <bpmndi:BPMNDiagram> e calcula
    coordenadas automáticas para todos os elementos.
    
    Strategy:
    - Distribui elementos horizontalmente na ordem em que aparecem
      no sequenceFlow (seguindo o fluxo).
    - Cada lane recebe uma faixa vertical de LANE_HEIGHT pixels.
    - Elementos são centralizados verticalmente dentro da lane.
    """
    try:
        # Remove existing diagram section if present
        bpmn_xml = re.sub(
            r'<bpmndi:BPMNDiagram.*?</bpmndi:BPMNDiagram>',
            '', bpmn_xml, flags=re.DOTALL
        )

        root = ET.fromstring(bpmn_xml)
    except ET.ParseError:
        # If XML is invalid, return as-is
        return bpmn_xml

    # Find the process element
    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        # Try within collaboration/participant
        process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return bpmn_xml

    process_id = process.get("id", "Process_1")

    # ── Collect all flow elements ────────────────────────────────
    flow_elements = {}  # id → (tag_type, element)
    for elem in process:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        elem_id = elem.get("id")
        if elem_id and tag not in ("sequenceFlow", "laneSet", "documentation"):
            flow_elements[elem_id] = (_classify_element(tag), elem)

    # ── Collect sequence flows ───────────────────────────────────
    flows = []
    for sf in process.findall(f"{{{BPMN_NS}}}sequenceFlow"):
        src = sf.get("sourceRef")
        tgt = sf.get("targetRef")
        sf_id = sf.get("id")
        if src and tgt and sf_id:
            flows.append((sf_id, src, tgt))

    # ── Identify lanes ──────────────────────────────────────────
    lane_set = process.find(f"{{{BPMN_NS}}}laneSet")
    lanes = []  # list of (lane_id, lane_name, [element_ids])
    element_to_lane = {}

    if lane_set is not None:
        for lane in lane_set.findall(f"{{{BPMN_NS}}}lane"):
            lane_id = lane.get("id", "")
            lane_name = lane.get("name", "Lane")
            refs = [ref.text for ref in lane.findall(f"{{{BPMN_NS}}}flowNodeRef") if ref.text]
            lanes.append((lane_id, lane_name, refs))
            for ref in refs:
                element_to_lane[ref] = lane_id
    
    if not lanes:
        # No lanes defined — create a single default lane
        all_ids = list(flow_elements.keys())
        lanes = [("Lane_default", "Processo", all_ids)]
        for eid in all_ids:
            element_to_lane[eid] = "Lane_default"

    # ── Order elements by flow ──────────────────────────────────
    # Build adjacency for topological-ish ordering
    successors = {}
    predecessors = {}
    for _, src, tgt in flows:
        successors.setdefault(src, []).append(tgt)
        predecessors.setdefault(tgt, []).append(src)

    # Find start elements (no predecessors)
    all_targets = {tgt for _, _, tgt in flows}
    all_sources = {src for _, src, _ in flows}
    start_ids = [eid for eid in flow_elements if eid not in all_targets]
    if not start_ids:
        start_ids = list(flow_elements.keys())[:1]

    # BFS ordering
    ordered = []
    visited = set()
    queue = list(start_ids)
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        if current in flow_elements:
            ordered.append(current)
        for nxt in successors.get(current, []):
            if nxt not in visited:
                queue.append(nxt)
    
    # Add any remaining unvisited elements
    for eid in flow_elements:
        if eid not in visited:
            ordered.append(eid)

    # ── Assign column positions per lane ────────────────────────
    lane_columns = {lid: 0 for lid, _, _ in lanes}
    element_positions = {}  # id → (x, y, w, h)

    lane_y_offsets = {}
    y_cursor = 0
    for lane_id, lane_name, _ in lanes:
        lane_y_offsets[lane_id] = y_cursor
        y_cursor += LANE_HEIGHT

    total_height = y_cursor

    for elem_id in ordered:
        if elem_id not in flow_elements:
            continue
        elem_type, _ = flow_elements[elem_id]
        lane_id = element_to_lane.get(elem_id, lanes[0][0])
        
        col = lane_columns.get(lane_id, 0)
        w, h = DIMS.get(elem_type, DIMS["task"])
        
        x = POOL_HEADER_WIDTH + H_GAP + col * (ELEMENT_WIDTH + H_GAP)
        lane_y = lane_y_offsets.get(lane_id, 0)
        y = lane_y + (LANE_HEIGHT - h) // 2

        element_positions[elem_id] = (x, y, w, h)
        lane_columns[lane_id] = col + 1

    # Calculate total width
    max_col = max(lane_columns.values()) if lane_columns else 1
    total_width = POOL_HEADER_WIDTH + (max_col + 1) * (ELEMENT_WIDTH + H_GAP)

    # ── Find collaboration & participant ────────────────────────
    collaboration = root.find(f"{{{BPMN_NS}}}collaboration")
    collab_id = collaboration.get("id", "Collaboration_1") if collaboration is not None else "Collaboration_1"
    
    participant = None
    participant_id = "Participant_1"
    if collaboration is not None:
        participant = collaboration.find(f"{{{BPMN_NS}}}participant")
        if participant is not None:
            participant_id = participant.get("id", "Participant_1")

    # ── Build BPMNDiagram ───────────────────────────────────────
    diagram = ET.SubElement(root, f"{{{BPMNDI_NS}}}BPMNDiagram", id="BPMNDiagram_1")
    plane = ET.SubElement(diagram, f"{{{BPMNDI_NS}}}BPMNPlane", id="BPMNPlane_1",
                          bpmnElement=collab_id)

    # Pool shape (participant)
    if participant is not None:
        pool_shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                                   id=f"{participant_id}_di",
                                   bpmnElement=participant_id,
                                   isHorizontal="true")
        ET.SubElement(pool_shape, f"{{{DC_NS}}}Bounds",
                      x="0", y="0",
                      width=str(total_width),
                      height=str(total_height))

    # Lane shapes
    for lane_id, lane_name, _ in lanes:
        lane_shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                                   id=f"{lane_id}_di",
                                   bpmnElement=lane_id,
                                   isHorizontal="true")
        lane_y = lane_y_offsets[lane_id]
        ET.SubElement(lane_shape, f"{{{DC_NS}}}Bounds",
                      x=str(POOL_HEADER_WIDTH), y=str(lane_y),
                      width=str(total_width - POOL_HEADER_WIDTH),
                      height=str(LANE_HEIGHT))

    # Element shapes
    for elem_id, (x, y, w, h) in element_positions.items():
        shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape",
                              id=f"{elem_id}_di",
                              bpmnElement=elem_id)
        ET.SubElement(shape, f"{{{DC_NS}}}Bounds",
                      x=str(x), y=str(y),
                      width=str(w), height=str(h))

    # Edge shapes (sequence flows)
    for sf_id, src, tgt in flows:
        if src in element_positions and tgt in element_positions:
            edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge",
                                 id=f"{sf_id}_di",
                                 bpmnElement=sf_id)
            sx, sy, sw, sh = element_positions[src]
            tx, ty, tw, th = element_positions[tgt]
            # Start from right-center of source, end at left-center of target
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(sx + sw), y=str(sy + sh // 2))
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(tx), y=str(ty + th // 2))

    # ── Serialize back to XML string ────────────────────────────
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return xml_str
