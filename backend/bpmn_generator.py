"""
BPMN Generator — Validates and wraps BPMN XML for Bizagi compatibility.
"""

import re


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
        'xmlns:bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
        'xmlns:bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
        'xmlns:dc': 'http://www.omg.org/spec/DD/20100524/DC',
        'xmlns:di': 'http://www.omg.org/spec/DD/20100524/DI',
    }
    
    for ns_prefix, ns_uri in required_ns.items():
        if ns_prefix not in bpmn_xml:
            # Add missing namespace to definitions tag
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
