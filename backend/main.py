"""
Mapeador Inteligente TJMG — FastAPI Backend
============================================
API com endpoints individuais para cada módulo de engenharia de processos.
Fluxo interativo: o usuário aprova cada módulo antes de avançar.
"""

import os
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from gemini_engine import (
    modulo_1_extracao_diagnostico,
    modulo_1_from_text,
    modulo_2_bpmn_as_is,
    modulo_3a_consultoria,
    modulo_3b_redesenho_to_be,
    modulo_4_pop,
)
from bpmn_generator import prepare_bpmn_file, validate_bpmn_structure
from pdf_generator import generate_pop_pdf

app = FastAPI(
    title="Mapeador Inteligente TJMG",
    description="API de mapeamento de processos com IA para o CEPROC/TJMG",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm", ".flac", ".aac"}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "gemini_configured": bool(os.getenv("GEMINI_API_KEY"))}


@app.get("/api/test-azure")
async def test_azure():
    """Endpoint de diagnóstico: testa a conexão com o Azure OpenAI."""
    from gemini_engine import get_client, GPT_DEPLOYMENT
    try:
        client = get_client()
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        response = client.chat.completions.create(
            model=GPT_DEPLOYMENT,
            messages=[{"role": "user", "content": "Diga apenas: OK"}],
            max_completion_tokens=10,
        )
        return {
            "status": "ok",
            "endpoint_used": endpoint[:60] + "...",
            "model": GPT_DEPLOYMENT,
            "response": response.choices[0].message.content,
        }
    except Exception as e:
        return {
            "status": "error",
            "endpoint_used": os.getenv("AZURE_OPENAI_ENDPOINT", "NOT SET")[:80],
            "error_type": type(e).__name__,
            "error_detail": str(e),
        }


@app.post("/api/test-whisper")
async def test_whisper(file: UploadFile = File(...)):
    """Endpoint de diagnóstico: testa o Whisper com um arquivo de áudio."""
    from gemini_engine import get_whisper_client, WHISPER_DEPLOYMENT
    try:
        client = get_whisper_client()
        content = await file.read()
        
        # Salvar em arquivo temporário
        ext = Path(file.filename).suffix.lower() or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=WHISPER_DEPLOYMENT,
                file=audio_file,
                language="pt",
            )
        
        os.unlink(tmp_path)
        return {
            "status": "ok",
            "deployment": WHISPER_DEPLOYMENT,
            "transcription_preview": transcription.text[:200],
        }
    except Exception as e:
        return {
            "status": "error",
            "deployment": WHISPER_DEPLOYMENT,
            "error_type": type(e).__name__,
            "error_detail": str(e)[:500],
        }

# ═══════════════════════════════════════════════════════════════════
# MÓDULO 1: Extração e Diagnóstico AS-IS
# ═══════════════════════════════════════════════════════════════════
@app.post("/api/modulo1")
async def run_modulo_1(file: UploadFile = File(...)):
    """Upload de áudio → Relatório de Descoberta (8 eixos)."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Formato não suportado: {ext}. Use: {', '.join(ALLOWED_EXTENSIONS)}")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(500, f"Erro ao salvar arquivo: {str(e)}")

    try:
        relatorio = await modulo_1_extracao_diagnostico(tmp_path, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 1: {str(e)}")
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass

    return {"success": True, "relatorio_descoberta": relatorio}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 1 (Texto): Transcrição colada pelo usuário
# ═══════════════════════════════════════════════════════════════════
class Modulo1TextRequest(BaseModel):
    transcricao: str

@app.post("/api/modulo1-text")
async def run_modulo_1_text(request: Modulo1TextRequest):
    """Texto transcrito → Relatório de Descoberta (8 eixos)."""
    if not request.transcricao.strip():
        raise HTTPException(400, "Texto da transcrição não pode ser vazio.")
    try:
        relatorio = await modulo_1_from_text(request.transcricao)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 1: {str(e)}")

    return {"success": True, "relatorio_descoberta": relatorio}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 2: Conversor BPMN-XML (AS-IS)
# ═══════════════════════════════════════════════════════════════════
class Modulo2Request(BaseModel):
    relatorio_descoberta: str

@app.post("/api/modulo2")
async def run_modulo_2(request: Modulo2Request):
    """Relatório de Descoberta → BPMN XML AS-IS para Bizagi."""
    try:
        bpmn_xml = await modulo_2_bpmn_as_is(request.relatorio_descoberta)
        bpmn_xml = prepare_bpmn_file(bpmn_xml)
        validation = validate_bpmn_structure(bpmn_xml)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 2: {str(e)}")

    return {
        "success": True,
        "bpmn_xml_as_is": bpmn_xml,
        "bpmn_validation": validation,
        "aviso_bizagi": "⚠️ Aviso Bizagi: Ao importar, as caixinhas aparecerão empilhadas no canto esquerdo. Arraste-as para as raias e as setas se conectarão."
    }


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3A: Consultoria (Sugestões de Melhoria)
# ═══════════════════════════════════════════════════════════════════
class Modulo3aRequest(BaseModel):
    relatorio_descoberta: str
    bpmn_xml_as_is: str

@app.post("/api/modulo3a")
async def run_modulo_3a(request: Modulo3aRequest):
    """Consultoria Lean → Gargalos, inovações e KPIs."""
    try:
        consultoria = await modulo_3a_consultoria(
            request.relatorio_descoberta,
            request.bpmn_xml_as_is
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 3A: {str(e)}")

    return {"success": True, "consultoria": consultoria}


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3B: Redesenho TO-BE (Novo XML)
# ═══════════════════════════════════════════════════════════════════
class Modulo3bRequest(BaseModel):
    relatorio_descoberta: str
    consultoria: str
    propostas_aprovadas: str

@app.post("/api/modulo3b")
async def run_modulo_3b(request: Modulo3bRequest):
    """Propostas aprovadas → BPMN XML TO-BE."""
    try:
        bpmn_xml = await modulo_3b_redesenho_to_be(
            request.relatorio_descoberta,
            request.consultoria,
            request.propostas_aprovadas
        )
        bpmn_xml = prepare_bpmn_file(bpmn_xml)
        validation = validate_bpmn_structure(bpmn_xml)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 3B: {str(e)}")

    return {
        "success": True,
        "bpmn_xml_to_be": bpmn_xml,
        "bpmn_validation": validation,
        "aviso_bizagi": "⚠️ Aviso Bizagi: Ao importar, as caixinhas aparecerão empilhadas no canto esquerdo. Arraste-as para as raias e as setas se conectarão."
    }


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 4: Geração do POP
# ═══════════════════════════════════════════════════════════════════
class Modulo4Request(BaseModel):
    bpmn_xml_to_be: str
    relatorio_descoberta: str

@app.post("/api/modulo4")
async def run_modulo_4(request: Modulo4Request):
    """BPMN TO-BE → POP em Markdown."""
    try:
        pop_texto = await modulo_4_pop(
            request.bpmn_xml_to_be,
            request.relatorio_descoberta
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro no Módulo 4: {str(e)}")

    return {"success": True, "pop_texto": pop_texto}


# ═══════════════════════════════════════════════════════════════════
# Downloads
# ═══════════════════════════════════════════════════════════════════
class BpmnDownloadRequest(BaseModel):
    bpmn_xml: str
    filename: str = "processo_mapeado"

@app.post("/api/download-bpmn")
async def download_bpmn(request: BpmnDownloadRequest):
    bpmn_content = prepare_bpmn_file(request.bpmn_xml)
    return Response(
        content=bpmn_content.encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{request.filename}.bpmn"'}
    )


class PdfDownloadRequest(BaseModel):
    pop_texto: str
    processo_nome: str = "Processo Mapeado"

@app.post("/api/download-pdf")
async def download_pdf(request: PdfDownloadRequest):
    try:
        pdf_bytes = generate_pop_pdf(request.pop_texto, request.processo_nome)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Erro ao gerar PDF: {str(e)}")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="POP_{request.processo_nome.replace(" ", "_")}.pdf"'}
    )


# ═══════════════════════════════════════════════════════════════════
# Serve Built Frontend (Production)
# ═══════════════════════════════════════════════════════════════════
STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If file exists in static dir, serve it
        file_path = STATIC_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA routing)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

