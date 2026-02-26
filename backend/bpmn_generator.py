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
    if not bpmn_xml.strip().startswith("<?xml"):
        bpmn_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + bpmn_xml

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
    """Basic structural validation of BPMN XML."""
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

    return {"valid": len(issues) == 0, "issues": issues}


# ═══════════════════════════════════════════════════════════════════
# AUTO-LAYOUT: Calcula coordenadas para BPMNDiagram
# ═══════════════════════════════════════════════════════════════════

# Layout constants — tuned for clear, readable diagrams
POOL_HEADER_WIDTH = 50       # Width of pool header (name sidebar)
LANE_HEADER_WIDTH = 30       # Width of lane header within pool
LANE_HEIGHT = 200            # Height of each lane
TASK_WIDTH = 140             # Width of task boxes
TASK_HEIGHT = 80             # Height of task boxes
EVENT_SIZE = 36              # Diameter of start/end events
GATEWAY_SIZE = 50            # Size of gateway diamonds
H_GAP = 80                   # Horizontal gap between elements
LEFT_MARGIN = 100            # Left margin before first element
TOP_MARGIN = 10              # Top margin within lane

# Dimensions lookup by element type
DIMS = {
    "task": (TASK_WIDTH, TASK_HEIGHT),
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
    Recebe XML BPMN 2.0 e recalcula o <bpmndi:BPMNDiagram> com
    coordenadas automáticas limpas e espaçadas.

    Strategy:
    1. Parse XML e coleta elementos, fluxos, e lanes
    2. Ordena elementos por BFS seguindo sequenceFlows
    3. Atribui coluna (posição horizontal) a cada elemento
    4. Centraliza verticalmente dentro de sua lane
    5. Gera waypoints para edges, com pontos intermediários para cross-lane
    """
    try:
        # Remove existing diagram section if present
        bpmn_xml = re.sub(
            r'<bpmndi:BPMNDiagram.*?</bpmndi:BPMNDiagram>',
            '', bpmn_xml, flags=re.DOTALL
        )
        root = ET.fromstring(bpmn_xml)
    except ET.ParseError:
        return bpmn_xml

    # ── Find the process element ────────────────────────────────
    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return bpmn_xml

    process_id = process.get("id", "Process_1")

    # ── Collect all flow elements ───────────────────────────────
    flow_elements = {}  # id → (tag_type, element)
    for elem in process:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        elem_id = elem.get("id")
        if elem_id and tag not in ("sequenceFlow", "laneSet", "documentation"):
            flow_elements[elem_id] = (_classify_element(tag), elem)

    if not flow_elements:
        return bpmn_xml

    # ── Collect sequence flows ──────────────────────────────────
    flows = []
    for sf in process.findall(f"{{{BPMN_NS}}}sequenceFlow"):
        src = sf.get("sourceRef")
        tgt = sf.get("targetRef")
        sf_id = sf.get("id")
        if src and tgt and sf_id:
            flows.append((sf_id, src, tgt))

    # ── Identify lanes ─────────────────────────────────────────
    lane_set = process.find(f"{{{BPMN_NS}}}laneSet")
    lanes = []
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
        all_ids = list(flow_elements.keys())
        lanes = [("Lane_default", "Processo", all_ids)]
        for eid in all_ids:
            element_to_lane[eid] = "Lane_default"

    # ── BFS ordering following flows ───────────────────────────
    successors = {}
    for _, src, tgt in flows:
        successors.setdefault(src, []).append(tgt)

    all_targets = {tgt for _, _, tgt in flows}
    start_ids = [eid for eid in flow_elements if eid not in all_targets]
    if not start_ids:
        start_ids = list(flow_elements.keys())[:1]

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

    # Add unvisited elements
    for eid in flow_elements:
        if eid not in visited:
            ordered.append(eid)

    # ── Assign global column for each element (by BFS order) ───
    # Elements in same column should never overlap
    element_column = {}
    global_col = 0
    for elem_id in ordered:
        element_column[elem_id] = global_col
        global_col += 1

    # ── Calculate positions ────────────────────────────────────
    lane_y_offsets = {}
    y_cursor = 0
    for lane_id, _, _ in lanes:
        lane_y_offsets[lane_id] = y_cursor
        y_cursor += LANE_HEIGHT

    total_height = y_cursor
    element_positions = {}  # id → (x, y, w, h)

    for elem_id in ordered:
        if elem_id not in flow_elements:
            continue
        elem_type, _ = flow_elements[elem_id]
        lane_id = element_to_lane.get(elem_id, lanes[0][0])
        col = element_column[elem_id]

        w, h = DIMS.get(elem_type, DIMS["task"])
        x = POOL_HEADER_WIDTH + LANE_HEADER_WIDTH + LEFT_MARGIN + col * (TASK_WIDTH + H_GAP)
        lane_y = lane_y_offsets.get(lane_id, 0)
        # Center vertically in lane
        y = lane_y + (LANE_HEIGHT - h) // 2

        element_positions[elem_id] = (x, y, w, h)

    # Calculate total width
    max_x = max((x + w) for x, y, w, h in element_positions.values()) if element_positions else 500
    total_width = max_x + LEFT_MARGIN

    # ── Find collaboration & participant ───────────────────────
    collaboration = root.find(f"{{{BPMN_NS}}}collaboration")
    collab_id = collaboration.get("id", "Collaboration_1") if collaboration is not None else "Collaboration_1"

    participant = None
    participant_id = "Participant_1"
    if collaboration is not None:
        participant = collaboration.find(f"{{{BPMN_NS}}}participant")
        if participant is not None:
            participant_id = participant.get("id", "Participant_1")

    # ── Build BPMNDiagram ──────────────────────────────────────
    diagram = ET.SubElement(root, f"{{{BPMNDI_NS}}}BPMNDiagram", id="BPMNDiagram_1")
    plane = ET.SubElement(diagram, f"{{{BPMNDI_NS}}}BPMNPlane", id="BPMNPlane_1",
                          bpmnElement=collab_id)

    # Pool shape (horizontal)
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

    # Edge shapes with smart waypoints
    for sf_id, src, tgt in flows:
        if src not in element_positions or tgt not in element_positions:
            continue

        edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge",
                             id=f"{sf_id}_di",
                             bpmnElement=sf_id)

        sx, sy, sw, sh = element_positions[src]
        tx, ty, tw, th = element_positions[tgt]

        # Source: right-center
        src_x = sx + sw
        src_y = sy + sh // 2
        # Target: left-center
        tgt_x = tx
        tgt_y = ty + th // 2

        src_lane = element_to_lane.get(src, "")
        tgt_lane = element_to_lane.get(tgt, "")

        if src_lane == tgt_lane or abs(src_y - tgt_y) < 20:
            # Same lane: simple straight line
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(src_x), y=str(src_y))
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(tgt_x), y=str(tgt_y))
        else:
            # Cross-lane: use orthogonal routing (right-angle connectors)
            mid_x = (src_x + tgt_x) // 2
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(src_x), y=str(src_y))
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(mid_x), y=str(src_y))
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(mid_x), y=str(tgt_y))
            ET.SubElement(edge, f"{{{DI_NS}}}waypoint",
                          x=str(tgt_x), y=str(tgt_y))

    # ── Serialize back to XML string ───────────────────────────
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return xml_str
