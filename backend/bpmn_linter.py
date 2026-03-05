"""
BPMN Linter — Motor de Validação baseado no Manual COGEPRO/TJMG.
================================================================
21 regras de validação organizadas em 3 grupos:
  Grupo 1: Visual e Arquivo (6 regras)
  Grupo 2: Nomenclatura e Semântica / NLP (10 regras)
  Grupo 3: Topologia / Grafo (5 regras)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from bpmn_parser import BpmnModel, BpmnWaypoint

# ── Try to load spaCy (graceful fallback) ───────────────────────────
_nlp = None

def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("pt_core_news_sm")
        except (ImportError, OSError):
            print("[WARN] spaCy pt_core_news_sm não disponível. Regras NLP usarão heurísticas simples.")
            _nlp = False
    return _nlp if _nlp is not False else None


# ── Result Data Classes ─────────────────────────────────────────────

@dataclass
class LintResult:
    level: str          # "CRITICAL", "ERROR", "WARN", "INFO"
    rule_id: str        # e.g., "TASK_BLACKLIST"
    message: str
    element_id: str = ""
    element_name: str = ""


@dataclass
class LintReport:
    results: list = field(default_factory=list)  # List[LintResult]
    has_critical: bool = False
    has_error: bool = False
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def add(self, result: LintResult):
        self.results.append(result)
        if result.level == "CRITICAL":
            self.has_critical = True
            self.error_count += 1
        elif result.level == "ERROR":
            self.has_error = True
            self.error_count += 1
        elif result.level == "WARN":
            self.warning_count += 1
        elif result.level == "INFO":
            self.info_count += 1

    def to_dict(self):
        return {
            "has_critical": self.has_critical,
            "has_error": self.has_error,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "results": [
                {
                    "level": r.level,
                    "rule_id": r.rule_id,
                    "message": r.message,
                    "element_id": r.element_id,
                    "element_name": r.element_name,
                }
                for r in self.results
            ],
        }


# ═══════════════════════════════════════════════════════════════════
# GRUPO 1: VALIDAÇÕES VISUAIS E DE ARQUIVO
# ═══════════════════════════════════════════════════════════════════

FILE_NAME_REGEX = r'^MOP \[(As Is|To Be)\] - .*?_\d{8}-\d{2}\.bpmn$'

# Minimum dimensions (width x height in px)
MIN_DIMS = {
    "task": (112, 72),
    "event": (30, 30),
    "gateway": (40, 40),
    "dataObject": (40, 50),
    "dataStore": (50, 50),
}


def _lint_file_name(filename: str, report: LintReport):
    """Rule FILE_NAME: Validate filename format."""
    if not re.match(FILE_NAME_REGEX, filename):
        report.add(LintResult(
            level="ERROR",
            rule_id="FILE_NAME",
            message=(
                f"Nome do arquivo inválido: '{filename}'. "
                f"Formato esperado: MOP [As Is|To Be] - NomeProcesso_YYYYMMDD-VV.bpmn"
            ),
        ))


def _lint_fonts(model: BpmnModel, report: LintReport):
    """Rule FONT_STYLE: Validate font names and sizes."""
    for elem_id, font_info in model.font_styles.items():
        font_name = font_info.get("name", "")
        font_size = font_info.get("size", 0)

        if font_name and font_name.lower() != "segoe ui":
            elem_name = ""
            if elem_id in model.elements:
                elem_name = model.elements[elem_id].name
            elif elem_id in model.annotations:
                elem_name = model.annotations[elem_id].name[:30]

            report.add(LintResult(
                level="WARN",
                rule_id="FONT_STYLE",
                message=f"Fonte '{font_name}' detectada. Padrão: Segoe UI.",
                element_id=elem_id,
                element_name=elem_name,
            ))

        # Size validation: header=10, others=8
        if font_size > 0:
            is_header = (model.header and elem_id == model.header.annotation_id)
            expected = 10 if is_header else 8
            if font_size != expected:
                report.add(LintResult(
                    level="WARN",
                    rule_id="FONT_STYLE",
                    message=f"Tamanho de fonte {font_size}pt, esperado {expected}pt.",
                    element_id=elem_id,
                ))


def _lint_dimensions(model: BpmnModel, report: LintReport):
    """Rules DIM_TASK, DIM_EVENT, DIM_GATEWAY, DIM_DATA: Validate element sizes."""
    for elem_id, elem in model.elements.items():
        if elem.bounds is None:
            continue

        w, h = elem.bounds.width, elem.bounds.height

        if elem.element_type == "task":
            min_w, min_h = MIN_DIMS["task"]
            if w < min_w or h < min_h:
                report.add(LintResult(
                    level="ERROR",
                    rule_id="DIM_TASK",
                    message=f"Tarefa com dimensões {w:.0f}x{h:.0f}px. Mínimo: {min_w}x{min_h}px.",
                    element_id=elem_id,
                    element_name=elem.name,
                ))

        elif elem.element_type == "event":
            min_w, min_h = MIN_DIMS["event"]
            if w < min_w or h < min_h:
                report.add(LintResult(
                    level="ERROR",
                    rule_id="DIM_EVENT",
                    message=f"Evento com dimensões {w:.0f}x{h:.0f}px. Mínimo: {min_w}x{min_h}px.",
                    element_id=elem_id,
                    element_name=elem.name,
                ))

        elif elem.element_type == "gateway":
            min_w, min_h = MIN_DIMS["gateway"]
            if w < min_w or h < min_h:
                report.add(LintResult(
                    level="ERROR",
                    rule_id="DIM_GATEWAY",
                    message=f"Gateway com dimensões {w:.0f}x{h:.0f}px. Mínimo: {min_w}x{min_h}px.",
                    element_id=elem_id,
                    element_name=elem.name,
                ))

    # Data objects / stores
    for obj_id, obj in model.data_objects.items():
        if obj.bounds is None:
            continue
        w, h = obj.bounds.width, obj.bounds.height
        key = "dataStore" if obj.data_type == "dataStore" else "dataObject"
        min_w, min_h = MIN_DIMS[key]
        if w < min_w or h < min_h:
            report.add(LintResult(
                level="WARN",
                rule_id="DIM_DATA",
                message=f"{key.replace('d', 'D', 1)} com dimensões {w:.0f}x{h:.0f}px. Mínimo: {min_w}x{min_h}px.",
                element_id=obj_id,
                element_name=obj.name,
            ))


# ═══════════════════════════════════════════════════════════════════
# GRUPO 2: NOMENCLATURA E SEMÂNTICA (NLP)
# ═══════════════════════════════════════════════════════════════════

# Blacklist for tasks (CRITICAL)
TASK_BLACKLIST = ["enviar", "encaminhar", "receber"]

# Common Portuguese infinitive endings
INFINITIVE_ENDINGS = ("ar", "er", "ir", "or")

# Common sector/department abbreviations (ALL CAPS expected)
KNOWN_SECTORS = {
    "CEPROC", "COGEPRO", "TJMG", "SEPLAG", "CGERAIS", "DIRFOR",
    "COGER", "SETIC", "ASCOM", "EJEF", "NUGEA", "NUPES",
}


def _is_infinitive(word: str) -> bool:
    """Check if a word looks like a Portuguese infinitive verb."""
    nlp = _get_nlp()
    if nlp:
        doc = nlp(word)
        for token in doc:
            if token.pos_ == "VERB" and token.morph.get("VerbForm") == ["Inf"]:
                return True
            # Fallback: if tagged as VERB and ends with infinitive pattern
            if token.pos_ == "VERB" and word.lower().endswith(INFINITIVE_ENDINGS):
                return True
        return False
    # Heuristic fallback
    return word.lower().endswith(INFINITIVE_ENDINGS)


def _starts_with_verb(text: str) -> bool:
    """Check if text starts with a verb."""
    nlp = _get_nlp()
    first_word = text.strip().split()[0] if text.strip() else ""
    if not first_word:
        return False
    if nlp:
        doc = nlp(first_word)
        return any(token.pos_ == "VERB" for token in doc)
    # Heuristic: check infinitive endings
    return first_word.lower().endswith(INFINITIVE_ENDINGS)


def _is_participle(word: str) -> bool:
    """Check if word is past participle (e.g., 'concluído', 'finalizado')."""
    nlp = _get_nlp()
    if nlp:
        doc = nlp(word)
        for token in doc:
            if token.morph.get("VerbForm") == ["Part"]:
                return True
    # Heuristic: common endings for past participle
    w = word.lower()
    return any(w.endswith(s) for s in ("ado", "ido", "ído", "sto", "to", "so"))


def _is_all_upper_word(text: str) -> bool:
    """Check if text is ALL UPPERCASE (allowing spaces/hyphens)."""
    return text == text.upper() and any(c.isalpha() for c in text)


def _is_sentence_case(text: str) -> bool:
    """Check if text is Sentence case (first letter upper, rest lower)."""
    if not text or not text[0].isupper():
        return False
    # Allow proper nouns and abbreviations within, just check first word
    words = text.split()
    if len(words) == 0:
        return False
    first = words[0]
    return first[0].isupper()


def _lint_header(model: BpmnModel, report: LintReport):
    """Rule HEADER_FORMAT: Validate header TextAnnotation structure."""
    if model.header is None:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Cabeçalho não encontrado. A primeira TextAnnotation deve conter: Título, Autor, Versão, Descrição.",
        ))
        return

    h = model.header
    if not h.title:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Cabeçalho sem Título.",
            element_id=h.annotation_id,
        ))

    if not h.author:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Cabeçalho sem Autor. Formato esperado: 'Nome Sobrenome - Setor'.",
            element_id=h.annotation_id,
        ))
    elif not re.search(r'\w+\s+\w+\s*-\s*\w+', h.author):
        report.add(LintResult(
            level="WARN",
            rule_id="HEADER_FORMAT",
            message=f"Autor '{h.author}' fora do formato esperado: 'Nome Sobrenome - Setor'.",
            element_id=h.annotation_id,
        ))

    if not h.version:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Cabeçalho sem Versão. Formato esperado: YYYYMMDD-VV.",
            element_id=h.annotation_id,
        ))
    elif not re.match(r'^\d{8}-\d{2}$', h.version.strip()):
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message=f"Versão '{h.version}' fora do formato esperado: YYYYMMDD-VV (ex: 20251117-01).",
            element_id=h.annotation_id,
        ))

    if not h.description:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Cabeçalho sem Descrição.",
            element_id=h.annotation_id,
        ))
    elif "[As Is]" not in h.description and "[To Be]" not in h.description:
        report.add(LintResult(
            level="ERROR",
            rule_id="HEADER_FORMAT",
            message="Descrição deve conter o identificador [As Is] ou [To Be].",
            element_id=h.annotation_id,
        ))


def _lint_pools(model: BpmnModel, report: LintReport):
    """Rule POOL_CASE: Only first letter capitalized (Sentence case)."""
    for pool in model.pools:
        name = pool.name.strip()
        if not name:
            continue
        if name == name.upper() and len(name) > 3:
            report.add(LintResult(
                level="WARN",
                rule_id="POOL_CASE",
                message=f"Nome do Pool '{name}' está em MAIÚSCULAS. Use apenas a primeira letra maiúscula.",
                element_id=pool.id,
                element_name=name,
            ))
        elif not name[0].isupper():
            report.add(LintResult(
                level="WARN",
                rule_id="POOL_CASE",
                message=f"Nome do Pool '{name}' deve iniciar com letra maiúscula.",
                element_id=pool.id,
                element_name=name,
            ))


def _lint_lanes(model: BpmnModel, report: LintReport):
    """Rule LANE_CASE: Sectors=ALL_UPPER, Roles=Capitalize."""
    for lane in model.lanes:
        name = lane.name.strip()
        if not name:
            continue

        # Check if it looks like a sector/abbreviation
        words = name.split()
        is_abbreviation = (
            len(words) == 1 and len(name) <= 8 and name == name.upper()
        ) or name.upper() in KNOWN_SECTORS

        if is_abbreviation:
            # Sector: should be ALL UPPER
            if name != name.upper():
                report.add(LintResult(
                    level="WARN",
                    rule_id="LANE_CASE",
                    message=f"Lane '{name}' parece ser uma sigla/setor. Use MAIÚSCULAS: '{name.upper()}'.",
                    element_id=lane.id,
                    element_name=name,
                ))
        else:
            # Role/position: Capitalize
            if not name[0].isupper():
                report.add(LintResult(
                    level="WARN",
                    rule_id="LANE_CASE",
                    message=f"Lane '{name}' (cargo/papel) deve iniciar com letra maiúscula.",
                    element_id=lane.id,
                    element_name=name,
                ))


def _lint_start_intermediate_events(model: BpmnModel, report: LintReport):
    """Rule EVENT_START_NOUN: Start/Intermediate events must be nouns, not verbs."""
    for elem_id, elem in model.elements.items():
        if elem.element_type != "event":
            continue

        subtype = elem.event_subtype
        if not subtype:
            continue

        # Only validate start and intermediate events
        is_start = "start" in subtype
        is_intermediate = "intermediate" in subtype
        if not (is_start or is_intermediate):
            continue

        name = elem.name.strip()
        if not name or name.lower() in ("início", "inicio"):
            continue

        if _starts_with_verb(name):
            report.add(LintResult(
                level="ERROR",
                rule_id="EVENT_START_NOUN",
                message=f"Evento de {'início' if is_start else 'intermediário'} '{name}' inicia com verbo. Use substantivo/expressão nominal.",
                element_id=elem_id,
                element_name=name,
            ))


def _lint_link_events(model: BpmnModel, report: LintReport):
    """Rule LINK_PAIR: Link throw/catch must have identical names."""
    link_throws = {}
    link_catches = {}

    for elem_id, elem in model.elements.items():
        if elem.element_type != "event":
            continue
        subtype = elem.event_subtype
        if "link" not in subtype:
            continue

        name = elem.name.strip()
        if "throw" in subtype:
            link_throws[name] = elem_id
        elif "catch" in subtype:
            link_catches[name] = elem_id

    # Check for unmatched throws
    for name, throw_id in link_throws.items():
        if name not in link_catches:
            report.add(LintResult(
                level="ERROR",
                rule_id="LINK_PAIR",
                message=f"Link Event de envio '{name}' não tem par de recepção correspondente.",
                element_id=throw_id,
                element_name=name,
            ))

    # Check for unmatched catches
    for name, catch_id in link_catches.items():
        if name not in link_throws:
            report.add(LintResult(
                level="ERROR",
                rule_id="LINK_PAIR",
                message=f"Link Event de recepção '{name}' não tem par de envio correspondente.",
                element_id=catch_id,
                element_name=name,
            ))


def _lint_tasks(model: BpmnModel, report: LintReport):
    """Rules TASK_INFINITIVE, TASK_BLACKLIST: Tasks must start with infinitive verb.
    CRITICAL error for blacklisted verbs."""
    for elem_id, elem in model.elements.items():
        if elem.element_type != "task":
            continue

        name = elem.name.strip()
        if not name:
            report.add(LintResult(
                level="WARN",
                rule_id="TASK_INFINITIVE",
                message="Tarefa sem nome.",
                element_id=elem_id,
            ))
            continue

        first_word = name.split()[0]

        # Blacklist check (CRITICAL)
        if first_word.lower() in TASK_BLACKLIST:
            report.add(LintResult(
                level="CRITICAL",
                rule_id="TASK_BLACKLIST",
                message=f"ERRO BLOQUEANTE: Tarefa '{name}' inicia com verbo proibido '{first_word}'. Verbos proibidos: {', '.join(TASK_BLACKLIST)}.",
                element_id=elem_id,
                element_name=name,
            ))
            continue

        # Infinitive check
        if not _is_infinitive(first_word):
            report.add(LintResult(
                level="ERROR",
                rule_id="TASK_INFINITIVE",
                message=f"Tarefa '{name}' deve iniciar com verbo no infinitivo (ex: Analisar, Elaborar, Verificar).",
                element_id=elem_id,
                element_name=name,
            ))


def _lint_gateways(model: BpmnModel, report: LintReport):
    """Rule GATEWAY_FORMAT: Gateways should be short questions, no bold."""
    for elem_id, elem in model.elements.items():
        if elem.element_type != "gateway":
            continue

        name = elem.name.strip()
        if not name:
            # Empty gateway names are ok for closing/converging gateways
            continue

        # Check bold formatting
        if elem.font_bold:
            report.add(LintResult(
                level="WARN",
                rule_id="GATEWAY_FORMAT",
                message=f"Gateway '{name}' com formatação em negrito. Gateways não devem estar em negrito.",
                element_id=elem_id,
                element_name=name,
            ))

        # Check if it's a question (should contain ?)
        if "?" not in name:
            report.add(LintResult(
                level="WARN",
                rule_id="GATEWAY_FORMAT",
                message=f"Gateway '{name}' deveria ser formulado como pergunta (com '?').",
                element_id=elem_id,
                element_name=name,
            ))


def _lint_end_events(model: BpmnModel, report: LintReport):
    """Rule EVENT_END_PARTICIPLE: End events should use past participle or conclusion nouns."""
    for elem_id, elem in model.elements.items():
        if elem.element_type != "event":
            continue

        if "end" not in elem.event_subtype:
            continue

        name = elem.name.strip()
        if not name or name.lower() in ("fim", "final", "término", "termino"):
            continue

        first_word = name.split()[0]
        # Check if it's participle or conclusion noun
        if not _is_participle(first_word):
            # Check for common conclusion nouns
            conclusion_nouns = {"fim", "final", "término", "conclusão", "encerramento",
                                "arquivamento", "cancelamento", "aprovação", "rejeição"}
            if first_word.lower() not in conclusion_nouns:
                report.add(LintResult(
                    level="WARN",
                    rule_id="EVENT_END_PARTICIPLE",
                    message=f"Evento de fim '{name}' deve usar particípio passado (ex: 'Concluído', 'Finalizado') ou substantivo de conclusão.",
                    element_id=elem_id,
                    element_name=name,
                ))


def _lint_annotations(model: BpmnModel, report: LintReport):
    """Rule ANNOTATION_IMPERATIVE: Annotations should not contain imperative verbs (like tasks)."""
    for ann_id, ann in model.annotations.items():
        # Skip header annotation
        if model.header and ann_id == model.header.annotation_id:
            continue

        text = ann.name.strip()
        if not text:
            continue

        first_word = text.split()[0]
        if _is_infinitive(first_word):
            report.add(LintResult(
                level="WARN",
                rule_id="ANNOTATION_IMPERATIVE",
                message=f"Anotação '{text[:50]}...' inicia com verbo de ação '{first_word}'. Isso a caracteriza como tarefa, não como anotação.",
                element_id=ann_id,
                element_name=text[:50],
            ))


# ═══════════════════════════════════════════════════════════════════
# GRUPO 3: VALIDAÇÕES TOPOLÓGICAS (NetworkX)
# ═══════════════════════════════════════════════════════════════════

def _lint_boundary_events(model: BpmnModel, report: LintReport):
    """Rule BOUNDARY_EVENT: Boundary events are PROHIBITED."""
    for elem_id, elem in model.elements.items():
        if elem.is_boundary:
            report.add(LintResult(
                level="ERROR",
                rule_id="BOUNDARY_EVENT",
                message=f"Boundary Event '{elem.name}' detectado (anexado a '{elem.attached_to}'). Eventos anexados são PROIBIDOS pelo manual.",
                element_id=elem_id,
                element_name=elem.name,
            ))


def _lint_gateway_pairing(model: BpmnModel, report: LintReport):
    """Rule GW_OPEN_CLOSE: Parallel/Inclusive gateways must have matching close."""
    if model.graph is None:
        return

    G = model.graph

    # Collect diverging (opening) gateways: out-degree > 1
    # Collect converging (closing) gateways: in-degree > 1
    for elem_id, elem in model.elements.items():
        if elem.element_type != "gateway":
            continue

        if elem.gateway_type in ("parallel", "inclusive"):
            out_deg = G.out_degree(elem_id) if elem_id in G else 0
            in_deg = G.in_degree(elem_id) if elem_id in G else 0

            if out_deg > 1:
                # This is a diverging gateway — look for matching converging gateway of same type
                found_match = False
                for other_id, other_elem in model.elements.items():
                    if other_id == elem_id:
                        continue
                    if other_elem.element_type != "gateway":
                        continue
                    if other_elem.gateway_type == elem.gateway_type:
                        other_in = G.in_degree(other_id) if other_id in G else 0
                        if other_in > 1:
                            found_match = True
                            break

                if not found_match:
                    report.add(LintResult(
                        level="ERROR",
                        rule_id="GW_OPEN_CLOSE",
                        message=f"Gateway {elem.gateway_type.upper()} '{elem.name}' diverge o fluxo mas não tem par de fechamento correspondente.",
                        element_id=elem_id,
                        element_name=elem.name,
                    ))


def _lint_loop_length(model: BpmnModel, report: LintReport):
    """Rule LOOP_LENGTH: Backward edges crossing > 5 nodes must use Link Events."""
    if model.graph is None:
        return

    G = model.graph

    # Find backward edges by checking if target appears before source in topological order
    # Since we may have cycles, use element positions (bounds X coords) as ordering proxy
    elem_x_order = {}
    for elem_id, elem in model.elements.items():
        if elem.bounds:
            elem_x_order[elem_id] = elem.bounds.x
        elif elem_id in model.bounds_map:
            elem_x_order[elem_id] = model.bounds_map[elem_id].x
        else:
            elem_x_order[elem_id] = 0

    for flow_id, flow in model.flows.items():
        src = flow.source_ref
        tgt = flow.target_ref

        if src not in elem_x_order or tgt not in elem_x_order:
            continue

        # Backward edge: target has lower X than source
        if elem_x_order[tgt] < elem_x_order[src]:
            # Count nodes between them (in the forward path)
            nodes_between = 0
            for eid, x_pos in elem_x_order.items():
                if elem_x_order[tgt] <= x_pos <= elem_x_order[src] and eid != src and eid != tgt:
                    nodes_between += 1

            if nodes_between > 5:
                report.add(LintResult(
                    level="ERROR",
                    rule_id="LOOP_LENGTH",
                    message=f"Loop de '{src}' para '{tgt}' cruza {nodes_between} nós (máx: 5). Use Eventos de Link para retornos longos.",
                    element_id=flow_id,
                    element_name=flow.name,
                ))


def _segments_intersect(p1: BpmnWaypoint, p2: BpmnWaypoint,
                        p3: BpmnWaypoint, p4: BpmnWaypoint) -> bool:
    """Check if line segment p1-p2 intersects with p3-p4 using cross products."""
    def cross(o, a, b):
        return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)

    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True

    return False


def _lint_edge_crossing(model: BpmnModel, report: LintReport):
    """Rule EDGE_CROSSING: Warn if edges cross geometrically."""
    edge_segments = []  # (flow_id, segment_index, p1, p2)

    for flow_id, waypoints in model.edge_waypoints.items():
        for i in range(len(waypoints) - 1):
            edge_segments.append((flow_id, i, waypoints[i], waypoints[i + 1]))

    crossings_found = set()

    for i in range(len(edge_segments)):
        for j in range(i + 1, len(edge_segments)):
            fid1, _, p1, p2 = edge_segments[i]
            fid2, _, p3, p4 = edge_segments[j]

            # Skip segments from same edge
            if fid1 == fid2:
                continue

            # Skip segments that share endpoints (connected flows)
            flow1 = model.flows.get(fid1)
            flow2 = model.flows.get(fid2)
            if flow1 and flow2:
                shared = {flow1.source_ref, flow1.target_ref} & {flow2.source_ref, flow2.target_ref}
                if shared:
                    continue

            if _segments_intersect(p1, p2, p3, p4):
                pair = tuple(sorted([fid1, fid2]))
                if pair not in crossings_found:
                    crossings_found.add(pair)

    if crossings_found:
        report.add(LintResult(
            level="WARN",
            rule_id="EDGE_CROSSING",
            message=f"Detectado(s) {len(crossings_found)} cruzamento(s) de setas no diagrama. Considere reorganizar o layout.",
        ))


# ═══════════════════════════════════════════════════════════════════
# MAIN LINT FUNCTION
# ═══════════════════════════════════════════════════════════════════

def lint_bpmn(model: BpmnModel, filename: str = "") -> LintReport:
    """
    Execute all 21 validation rules on a parsed BpmnModel.

    Args:
        model: Parsed BPMN model from bpmn_parser.parse_bpmn()
        filename: Original filename (for file name validation)

    Returns:
        LintReport with all results sorted by severity.
    """
    report = LintReport()

    # ── Grupo 1: Visual/Arquivo ─────────────────────────────────
    if filename:
        _lint_file_name(filename, report)
    _lint_fonts(model, report)
    _lint_dimensions(model, report)

    # ── Grupo 2: Nomenclatura/Semântica ─────────────────────────
    _lint_header(model, report)
    _lint_pools(model, report)
    _lint_lanes(model, report)
    _lint_start_intermediate_events(model, report)
    _lint_link_events(model, report)
    _lint_tasks(model, report)
    _lint_gateways(model, report)
    _lint_end_events(model, report)
    _lint_annotations(model, report)

    # ── Grupo 3: Topologia ──────────────────────────────────────
    _lint_boundary_events(model, report)
    _lint_gateway_pairing(model, report)
    _lint_loop_length(model, report)
    _lint_edge_crossing(model, report)

    # Sort results: CRITICAL first, then ERROR, WARN, INFO
    severity_order = {"CRITICAL": 0, "ERROR": 1, "WARN": 2, "INFO": 3}
    report.results.sort(key=lambda r: severity_order.get(r.level, 4))

    return report
