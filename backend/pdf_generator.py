"""
PDF Generator — Gera o PDF do Procedimento Operacional Padrão (POP)
com identidade visual do TJMG.
"""

import io
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)


# TJMG Color Palette
TJMG_VINHO = HexColor("#6B1D2A")
TJMG_AZUL = HexColor("#1B2A4A")
TJMG_DOURADO = HexColor("#C5A55A")
TJMG_CINZA = HexColor("#666666")
TJMG_CINZA_CLARO = HexColor("#F5F5F7")


def _get_styles():
    """Create custom paragraph styles for TJMG brand."""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='TJMGTitle',
        fontSize=20,
        leading=24,
        textColor=TJMG_VINHO,
        alignment=TA_CENTER,
        spaceAfter=6*mm,
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='TJMGSubtitle',
        fontSize=11,
        leading=14,
        textColor=TJMG_AZUL,
        alignment=TA_CENTER,
        spaceAfter=12*mm,
        fontName='Helvetica'
    ))
    
    styles.add(ParagraphStyle(
        name='TJMGHeading',
        fontSize=13,
        leading=16,
        textColor=TJMG_VINHO,
        spaceBefore=8*mm,
        spaceAfter=4*mm,
        fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='TJMGBody',
        fontSize=10,
        leading=14,
        textColor=HexColor("#333333"),
        alignment=TA_JUSTIFY,
        spaceAfter=3*mm,
        fontName='Helvetica'
    ))
    
    styles.add(ParagraphStyle(
        name='TJMGFooter',
        fontSize=8,
        leading=10,
        textColor=TJMG_CINZA,
        alignment=TA_CENTER,
        fontName='Helvetica'
    ))
    
    return styles


def generate_pop_pdf(pop_texto: str, processo_nome: str = "Processo Mapeado") -> bytes:
    """
    Generates a PDF for the POP document with TJMG branding.
    Returns PDF as bytes.
    """
    buffer = io.BytesIO()
    styles = _get_styles()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
        leftMargin=2.5*cm,
        rightMargin=2.5*cm,
        title=f"POP - {processo_nome}",
        author="CEPROC/TJMG - Mapeador Inteligente"
    )
    
    elements = []
    
    # ── Header ──────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "TRIBUNAL DE JUSTIÇA DO ESTADO DE MINAS GERAIS",
        styles['TJMGTitle']
    ))
    
    elements.append(Paragraph(
        "CEPROC — Centro de Estudos de Procedimentos",
        styles['TJMGSubtitle']
    ))
    
    # Divider line
    elements.append(HRFlowable(
        width="100%", thickness=2, color=TJMG_DOURADO,
        spaceAfter=8*mm, spaceBefore=2*mm
    ))
    
    # Document title
    elements.append(Paragraph(
        "PROCEDIMENTO OPERACIONAL PADRÃO (POP)",
        ParagraphStyle(
            'POPTitle',
            fontSize=14,
            leading=18,
            textColor=TJMG_AZUL,
            alignment=TA_CENTER,
            spaceAfter=4*mm,
            fontName='Helvetica-Bold'
        )
    ))
    
    elements.append(Paragraph(
        processo_nome,
        ParagraphStyle(
            'ProcessoNome',
            fontSize=12,
            leading=16,
            textColor=TJMG_VINHO,
            alignment=TA_CENTER,
            spaceAfter=6*mm,
            fontName='Helvetica-Bold'
        )
    ))
    
    # Metadata table
    today = datetime.now().strftime("%d/%m/%Y")
    meta_data = [
        ["Data de Elaboração:", today, "Versão:", "1.0"],
        ["Elaborado por:", "CEPROC/TJMG", "Aprovado por:", "_______________"],
    ]
    
    meta_table = Table(meta_data, colWidths=[3.5*cm, 5*cm, 3.5*cm, 5*cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), TJMG_AZUL),
        ('TEXTCOLOR', (2, 0), (2, -1), TJMG_AZUL),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, TJMG_CINZA_CLARO),
        ('BACKGROUND', (0, 0), (0, -1), TJMG_CINZA_CLARO),
        ('BACKGROUND', (2, 0), (2, -1), TJMG_CINZA_CLARO),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10*mm))
    
    # Divider
    elements.append(HRFlowable(
        width="100%", thickness=1, color=TJMG_DOURADO,
        spaceAfter=6*mm
    ))
    
    # ── POP Content ─────────────────────────────────────────────────────
    # Parse the POP text into sections
    sections = _parse_pop_sections(pop_texto)
    
    for section_title, section_content in sections:
        elements.append(Paragraph(section_title, styles['TJMGHeading']))
        
        # Process content paragraphs
        for paragraph in section_content.split('\n'):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Clean markdown bold/italic markers
            paragraph = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', paragraph)
            paragraph = re.sub(r'\*(.*?)\*', r'<i>\1</i>', paragraph)
            
            # Bullet points
            if paragraph.startswith('- ') or paragraph.startswith('• '):
                paragraph = '• ' + paragraph[2:]
            
            elements.append(Paragraph(paragraph, styles['TJMGBody']))
    
    # ── Footer ──────────────────────────────────────────────────────────
    elements.append(Spacer(1, 15*mm))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=TJMG_DOURADO,
        spaceAfter=4*mm
    ))
    elements.append(Paragraph(
        f"Documento gerado automaticamente pelo Mapeador Inteligente TJMG — CEPROC — {today}",
        styles['TJMGFooter']
    ))
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _parse_pop_sections(text: str) -> list:
    """
    Parses POP text into (title, content) pairs.
    Handles markdown-style headings (## or numbered sections).
    """
    sections = []
    current_title = "Conteúdo"
    current_content = []
    
    for line in text.split('\n'):
        stripped = line.strip()
        
        # Check for section headers
        header_match = re.match(
            r'^(?:#{1,3}\s+)?(?:\d+[\.\)]\s*)?(.+?)$', stripped
        )
        
        is_header = False
        if stripped.startswith('#'):
            is_header = True
            stripped = re.sub(r'^#{1,3}\s+', '', stripped)
        elif re.match(r'^\d+\.\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]', stripped):
            is_header = True
        
        if is_header and stripped:
            # Save previous section
            if current_content:
                sections.append((current_title, '\n'.join(current_content)))
            current_title = stripped
            current_content = []
        else:
            current_content.append(line)
    
    # Save last section
    if current_content:
        sections.append((current_title, '\n'.join(current_content)))
    
    return sections
