"""
LLM Engine — 4 Módulos de Engenharia de Processos CEPROC/TJMG
==============================================================
Usa Azure OpenAI (Microsoft Foundry) para todas as chamadas LLM.
Para áudio, usa o Whisper do Azure para transcrição e depois GPT para análise.

Módulo 1: Extração e Diagnóstico AS-IS (8 eixos)
Módulo 2: Conversor BPMN-XML para Bizagi (AS-IS)
Módulo 3: Consultoria e Redesenho TO-BE (Fase A / Fase B)
Módulo 4: Geração do POP

REGRA DE OURO: Cada módulo é executado individualmente.
O usuário aprova antes de avançar ao próximo.
"""

import os
import re
from datetime import datetime
from openai import AzureOpenAI


def get_client():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        raise ValueError(
            "AZURE_OPENAI_ENDPOINT e AZURE_OPENAI_API_KEY não configuradas. "
            "Defina no arquivo .env"
        )
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-12-01-preview",
    )


def get_whisper_client():
    """Client separado para Whisper, que usa api_version diferente."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not endpoint or not api_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT e AZURE_OPENAI_API_KEY não configuradas.")
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-06-01",
    )


# Deployment names — ajuste aqui se seus deployments tiverem nomes diferentes
GPT_DEPLOYMENT = "gpt-5.2-chat"
WHISPER_DEPLOYMENT = "whisper"


def _get_version_as_is():
    return datetime.now().strftime("%Y%m%d") + "-01"


def _get_version_to_be():
    return datetime.now().strftime("%Y%m%d") + "-02"


def _chat(client, system_prompt: str, user_prompt: str) -> str:
    """Helper: faz uma chamada chat completion no Azure OpenAI."""
    response = client.chat.completions.create(
        model=GPT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=16000,
    )
    return response.choices[0].message.content


SYSTEM_PROMPT = (
    "Você é um Engenheiro de Processos Sênior do TJMG, especialista em "
    "BPMN 2.0, Metodologia Lean e Gestão do Conhecimento. Você trabalha no "
    "CEPROC — Centro de Estudos de Procedimentos do Tribunal de Justiça de "
    "Minas Gerais."
)


# ═══════════════════════════════════════════════════════════════════
# TRANSCRIÇÃO DE ÁUDIO (Whisper)
# ═══════════════════════════════════════════════════════════════════
async def _transcribe_audio(audio_path: str) -> str:
    """Transcreve áudio usando o Whisper deployment do Azure OpenAI."""
    whisper_client = get_whisper_client()
    with open(audio_path, "rb") as audio_file:
        transcription = whisper_client.audio.transcriptions.create(
            model=WHISPER_DEPLOYMENT,
            file=audio_file,
            language="pt",
        )
    return transcription.text


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 1: EXTRAÇÃO E DIAGNÓSTICO AS-IS
# ═══════════════════════════════════════════════════════════════════
_MODULO_1_PROMPT = """Com base na transcrição da entrevista de mapeamento abaixo, gere o "Relatório de Descoberta" estruturado nos 8 eixos:

--- TRANSCRIÇÃO DA ENTREVISTA ---
{transcricao}
--- FIM DA TRANSCRIÇÃO ---

AÇÃO: Filtre os dados e gere o relatório nos 8 eixos abaixo:

## 1. Início do Processo
Gatilhos (o que dispara o processo), atores envolvidos, insumos necessários e normativos aplicáveis.

## 2. Atividades Principais
Linha do tempo das atividades, atores responsáveis, sistemas utilizados e documentos gerados/consumidos.

## 3. Custo e Produtividade
Volume de trabalho (quantidade mensal/diária), tempo médio por atividade/processo e tamanho da equipe.

## 4. Restrições e Limitações
Gargalos identificados, caminhos de exceção e situações problemáticas.

## 5. Fim do Processo
Última atividade executada, saídas/produtos finais e cliente final (quem recebe).

## 6. Impacto
Importância estratégica do processo e riscos da não execução.

## 7. Avaliação
Indicadores existentes e existência de Procedimentos Operacionais Padrão (POPs).

## 8. Expectativa de Melhoria
Dores da equipe e sugestões de melhoria relatadas pelos servidores.

REGRA IMPORTANTE: Se faltar alguma informação para qualquer eixo, preencha com: [⚠️ Informação não coletada]

Gere o relatório completo em Markdown, de forma clara e profissional."""


async def modulo_1_extracao_diagnostico(audio_path: str, filename: str) -> str:
    """Recebe o áudio → transcreve com Whisper → gera Relatório de Descoberta."""
    client = get_client()

    # Passo 1: Transcrever com Whisper
    transcricao = await _transcribe_audio(audio_path)

    # Passo 2: Analisar com GPT
    prompt = _MODULO_1_PROMPT.format(transcricao=transcricao)
    return _chat(client, SYSTEM_PROMPT, prompt)


async def modulo_1_from_text(transcricao: str) -> str:
    """Recebe texto transcrito colado pelo usuário → gera Relatório de Descoberta."""
    client = get_client()
    prompt = _MODULO_1_PROMPT.format(transcricao=transcricao)
    return _chat(client, SYSTEM_PROMPT, prompt)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 2: CONVERSOR BPMN-XML PARA BIZAGI (AS-IS)
# ═══════════════════════════════════════════════════════════════════
async def modulo_2_bpmn_as_is(relatorio_descoberta: str) -> str:
    client = get_client()
    version = _get_version_as_is()

    prompt = f"""Com base no Relatório de Descoberta abaixo, converta o fluxo AS-IS em código-fonte XML BPMN 2.0 válido e perfeito (<bpmn:definitions>) para importação no Bizagi Modeler.

--- RELATÓRIO DE DESCOBERTA (MÓDULO 1) ---
{relatorio_descoberta}
--- FIM DO RELATÓRIO ---

REGRAS OBRIGATÓRIAS:
1. **Versão**: Use "{version}" como ID da versão.
2. **Documentação** (<bpmn:documentation>): Inicie com "O modelo de processo atual (As Is) descreve ".
3. **Nomenclatura BPMN**:
   - Tarefas: Verbos no Infinitivo (ex: "Receber petição", "Analisar documento").
   - Gateways: Formulados como perguntas (ex: "Documento está correto?").
4. **Estrutura obrigatória**:
   - 1 Pool principal (com o nome do processo).
   - Swimlanes (raias) para cada ator/setor identificado.
   - Setas (sequenceFlow com sourceRef/targetRef) rigorosamente conectadas.
   - StartEvent, EndEvent, Tasks, ExclusiveGateways conforme o fluxo.
5. **Namespaces**: 
   - xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
   - xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
   - xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
   - xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
6. **Inclua o BPMNDiagram** com coordenadas (x, y) para cada shape e edge.

OUTPUT: Gere APENAS o XML válido, sem explicações, sem marcadores de código, sem texto antes ou depois. Comece com <?xml e termine com </bpmn:definitions>."""

    result = _chat(client, SYSTEM_PROMPT, prompt)

    # Remove markdown code fences if present
    xml_text = result.strip()
    if xml_text.startswith("```"):
        xml_text = re.sub(r'^```(?:xml)?\s*\n?', '', xml_text)
        xml_text = re.sub(r'\n?\s*```$', '', xml_text)

    return xml_text


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3A: CONSULTORIA (Sugestões de Melhoria)
# ═══════════════════════════════════════════════════════════════════
async def modulo_3a_consultoria(relatorio_descoberta: str, bpmn_as_is: str) -> str:
    client = get_client()

    prompt = f"""Com base no Relatório de Descoberta e no fluxo BPMN AS-IS abaixo, execute a consultoria de redesenho:

--- RELATÓRIO DE DESCOBERTA ---
{relatorio_descoberta}
--- FIM ---

--- BPMN XML AS-IS ---
{bpmn_as_is[:3000]}
--- FIM ---

EXECUTE AS 3 AÇÕES:

## 1. Gargalos Identificados (Visão Lean)
Aponte cada gargalo encontrado no processo, explicando:
- Onde está o gargalo
- Por que é um problema
- Impacto estimado (tempo perdido, retrabalho, risco)

## 2. Inovações Sugeridas
Sugira melhorias concretas, como:
- Uso do PJe (Processo Judicial Eletrônico)
- Uso do SEI (Sistema Eletrônico de Informações)
- Automações possíveis (RPA, templates, workflows)
- Eliminação de etapas redundantes
- Unificação de handoffs

Para cada sugestão, explique o benefício esperado.

## 3. KPIs Propostos (Metas do CNJ)
Sugira 3 KPIs (Indicadores-Chave de Desempenho) alinhados às Metas do CNJ, indicando:
- Nome do KPI
- Fórmula de cálculo
- Meta sugerida
- Frequência de medição

Numere cada proposta de melhoria para que o usuário possa selecionar quais aprovar.
Apresente de forma clara e profissional em Markdown."""

    return _chat(client, SYSTEM_PROMPT, prompt)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3B: REDESENHO TO-BE (Novo XML)
# ═══════════════════════════════════════════════════════════════════
async def modulo_3b_redesenho_to_be(
    relatorio_descoberta: str,
    consultoria: str,
    propostas_aprovadas: str
) -> str:
    client = get_client()
    version = _get_version_to_be()

    prompt = f"""Com base no relatório, na consultoria e nas propostas APROVADAS pelo usuário, gere o NOVO código XML BPMN 2.0 (TO-BE).

--- RELATÓRIO DE DESCOBERTA ---
{relatorio_descoberta}
--- FIM ---

--- CONSULTORIA E SUGESTÕES ---
{consultoria}
--- FIM ---

--- PROPOSTAS APROVADAS PELO USUÁRIO ---
{propostas_aprovadas}
--- FIM ---

REGRAS OBRIGATÓRIAS:
1. **Versão**: Use "{version}" como ID da versão.
2. **Documentação** (<bpmn:documentation>): Inicie com "O modelo de processo proposto (To Be) descreve ".
3. **Nomenclatura BPMN**:
   - Tarefas: Verbos no Infinitivo.
   - Gateways: Formulados como perguntas.
4. **Estrutura obrigatória**:
   - 1 Pool principal (com o nome do processo otimizado).
   - Swimlanes (raias) para cada ator/setor.
   - Setas (sequenceFlow) rigorosamente conectadas.
   - Incorpore TODAS as melhorias/propostas aprovadas no novo fluxo.
5. **Namespaces**: mesmos do padrão BPMN 2.0.
6. **Inclua o BPMNDiagram** com coordenadas para cada shape e edge.

OUTPUT: Gere APENAS o XML válido, sem explicações, sem marcadores de código. Comece com <?xml e termine com </bpmn:definitions>."""

    result = _chat(client, SYSTEM_PROMPT, prompt)

    xml_text = result.strip()
    if xml_text.startswith("```"):
        xml_text = re.sub(r'^```(?:xml)?\s*\n?', '', xml_text)
        xml_text = re.sub(r'\n?\s*```$', '', xml_text)

    return xml_text


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 4: GERAÇÃO DO POP
# ═══════════════════════════════════════════════════════════════════
async def modulo_4_pop(bpmn_to_be: str, relatorio_descoberta: str) -> str:
    client = get_client()
    version = _get_version_to_be()

    prompt = f"""Traduza o fluxo BPMN TO-BE abaixo em um POP (Procedimento Operacional Padrão) didático em Markdown. NÃO use jargões BPMN — o POP é para o servidor que executa o trabalho no dia a dia.

--- BPMN XML TO-BE ---
{bpmn_to_be[:5000]}
--- FIM ---

--- RELATÓRIO DE DESCOBERTA (contexto) ---
{relatorio_descoberta[:3000]}
--- FIM ---

ESTRUTURA OBRIGATÓRIA DO POP:

# TJMG - PROCEDIMENTO OPERACIONAL PADRÃO

## 1. Identificação
| Campo | Valor |
|-------|-------|
| Nome do Processo | [extrair do fluxo] |
| Setor(es) Envolvido(s) | [listar] |
| Versão | {version} |
| Data | {datetime.now().strftime("%d/%m/%Y")} |

## 2. Objetivo
[Descrever a finalidade do processo de forma clara e direta]

## 3. Sistemas e Insumos
[Listar todos os sistemas (PJe, SEI, etc.) e insumos necessários]

## 4. Passo a Passo

Para cada etapa, use o formato:

### Passo N — [Nome da Etapa]
| Campo | Descrição |
|-------|-----------|
| **Quem** | [Ator responsável] |
| **Onde** | [Sistema/local] |
| **Como Fazer** | [Instruções detalhadas] |
| **Regras** | [Condições, exceções, decisões] |

## 5. Pontos de Atenção
[Alertas sobre erros comuns, cuidados especiais, prazos]

## 6. Indicadores
[KPIs validados no módulo anterior, com nome, fórmula e meta]

---
*Documento gerado pelo Mapeador Inteligente — CEPROC/TJMG*

Gere o POP completo em Markdown, de forma clara, didática e profissional."""

    return _chat(client, SYSTEM_PROMPT, prompt)
