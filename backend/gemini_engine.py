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
# TRANSCRIÇÃO DE ÁUDIO (Whisper + ffmpeg preprocessing + chunking)
# ═══════════════════════════════════════════════════════════════════
import subprocess
import tempfile as _tempfile
import glob

MAX_WHISPER_SIZE = 24 * 1024 * 1024  # 24MB limit
CHUNK_DURATION = 600  # 10 minutes per chunk


def _convert_audio_to_mp3(input_path: str) -> str:
    """Converte áudio/vídeo para MP3 mono otimizado via ffmpeg.
    Bitrate reduzido para 64kbps para minimizar tamanho.
    """
    output_path = input_path.rsplit(".", 1)[0] + "_converted.mp3"
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vn",                    # remove video
        "-acodec", "libmp3lame",  # MP3 codec
        "-ab", "64k",             # 64kbps (suficiente para voz)
        "-ar", "16000",           # 16kHz (otimizado para speech)
        "-ac", "1",               # mono
        "-y",                     # overwrite
        output_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
        return output_path
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[WARN] ffmpeg falhou: {e}, usando arquivo original")
        return input_path


def _split_audio_chunks(mp3_path: str) -> list[str]:
    """Divide o áudio em chunks de CHUNK_DURATION segundos usando ffmpeg."""
    base = mp3_path.rsplit(".", 1)[0]
    pattern = f"{base}_chunk_%03d.mp3"
    cmd = [
        "ffmpeg", "-i", mp3_path,
        "-f", "segment",
        "-segment_time", str(CHUNK_DURATION),
        "-acodec", "libmp3lame",
        "-ab", "64k",
        "-ar", "16000",
        "-ac", "1",
        "-y",
        pattern
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Chunking falhou: {e}")
        return [mp3_path]
    
    chunks = sorted(glob.glob(f"{base}_chunk_*.mp3"))
    return chunks if chunks else [mp3_path]


def _transcribe_single_file(whisper_client, file_path: str) -> str:
    """Transcreve um único arquivo de áudio com Whisper."""
    with open(file_path, "rb") as audio_file:
        transcription = whisper_client.audio.transcriptions.create(
            model=WHISPER_DEPLOYMENT,
            file=audio_file,
            language="pt",
        )
    if hasattr(transcription, 'text'):
        return transcription.text
    return str(transcription)


async def _transcribe_audio(audio_path: str) -> str:
    """Transcreve áudio usando o Whisper deployment do Azure OpenAI.
    Pipeline: ffmpeg convert → check size → chunk if needed → transcribe → merge.
    """
    whisper_client = get_whisper_client()
    converted_path = _convert_audio_to_mp3(audio_path)
    cleanup_files = []
    
    try:
        if converted_path != audio_path:
            cleanup_files.append(converted_path)
        
        file_size = os.path.getsize(converted_path)
        print(f"[INFO] Áudio convertido: {file_size // (1024*1024)}MB")
        
        if file_size <= MAX_WHISPER_SIZE:
            # Arquivo pequeno: transcreve direto
            return _transcribe_single_file(whisper_client, converted_path)
        
        # Arquivo grande: dividir em chunks
        print(f"[INFO] Arquivo grande ({file_size // (1024*1024)}MB), dividindo em chunks de {CHUNK_DURATION}s...")
        chunks = _split_audio_chunks(converted_path)
        cleanup_files.extend(chunks)
        
        all_texts = []
        for i, chunk_path in enumerate(chunks):
            chunk_size = os.path.getsize(chunk_path)
            print(f"[INFO] Transcrevendo chunk {i+1}/{len(chunks)} ({chunk_size // (1024*1024)}MB)...")
            text = _transcribe_single_file(whisper_client, chunk_path)
            all_texts.append(text)
        
        return "\n\n".join(all_texts)
    
    finally:
        for f in cleanup_files:
            try:
                os.unlink(f)
            except:
                pass


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 1: EXTRAÇÃO E DIAGNÓSTICO AS-IS
# ═══════════════════════════════════════════════════════════════════
_MODULO_1_PROMPT = """Você é um analista especialista em mapeamento e documentação de processos de trabalho organizacionais.

Sua tarefa é analisar a transcrição de uma entrevista com colaboradores de um setor e extrair as informações necessárias para preencher uma **Descrição do Processo de Trabalho (DPT)**,

--- TRANSCRIÇÃO DA ENTREVISTA ---
{transcricao}
--- FIM DA TRANSCRIÇÃO ---

### REGRAS DE EXTRAÇÃO

- **NEGÓCIO**: Busque descrições sobre a missão, atuação ou responsabilidade geral do setor — não do processo específico, mas da área como um todo.
- **FINALIDADE**: Busque frases como "o objetivo é", "o processo existe para", "garantir que", "assegurar que".
- **CONCEITOS E DEFINIÇÕES**: Capture qualquer definição de termo técnico, sigla explicada ou conceito que os entrevistados definirem explicitamente.
- **CLIENTES**: Identifique quem recebe o produto ou serviço do processo — pode ser um setor interno, órgão externo ou cidadão.
- **NORMAS REGULADORAS**: Capture referências a leis, portarias, resoluções, instruções normativas ou políticas internas.
- **DESCRIÇÕES DE ENTRADA**: O que desencadeia o processo? Qual documento, evento ou solicitação dá início ao fluxo?
- **PRINCIPAIS ETAPAS**: Mapeie cada passo do fluxo de trabalho em ordem. Preserve desvios condicionais ("se X, então Y") como `condicoes`.
- **DESCRIÇÕES DE SAÍDA**: Qual é o produto final entregue? O que indica que o processo foi concluído?
- **ATORES**: Todo cargo, pessoa ou entidade que executa ou participa do processo.
- **SISTEMAS E INFRAESTRUTURA**: Qualquer software, plataforma, sistema institucional, ferramenta de comunicação ou equipamento mencionado.
- **EXPECTATIVA DE MELHORIA**: Menções a problemas que serão resolvidos, padronizações esperadas ou melhorias já implementadas.
- **DOCUMENTOS E INDICADORES**: Formulários, planilhas, comprovantes, termos, relatórios e métricas citados.
- **PONTOS SENSÍVEIS**: Problemas, riscos, inconsistências, gargalos, uso inadequado de ferramentas, ausência de padronização, falhas de controle.
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
# MÓDULO 2: CONVERSOR BPMN-XML PARA BIZAGI (AS-IS) — CHAIN-OF-THOUGHT
# ═══════════════════════════════════════════════════════════════════

_STEP1_STRUCTURE_PROMPT = """# 🔄 Prompt Especialista: DPT JSON → BPMN JSON

Converte um JSON de DPT (Descrição do Processo de Trabalho) em um **JSON otimizado para BPMN** com coordenadas, waypoints e sequência de fluxo bem definida.

---

## 🎯 Objetivo

Gerar um JSON especializado que será usado pelo gerador BPMN para criar diagramas com:
- Coordenadas corretas (início/fim nas bordas dos elementos)
- Waypoints para setas (passando corretamente entre raias)
- Transições inter-raias identificadas
- Sincronizações claras
- Sequência de fluxo bem estruturada

---

## 📋 PROMPT PARA COPIAR E COLAR


Você é um especialista em BPMN 2.0 e modelagem de processos.

Sua tarefa é analisar um JSON de DPT (Descrição do Processo de Trabalho) 
e convertê-lo em um JSON otimizado para geração de diagramas BPMN com 
coordenadas precisas, waypoints corretos e fluxo entre raias bem estruturado.

REGRAS IMPORTANTES:

1. ESTRUTURA DE RAIAS (LANES)
   - Identifique todos os atores/responsáveis
   - Ordene de cima para baixo em ordem lógica
   - Calcule posição Y para cada raia: Y = 50 + (índice * 200)
   - Altura da raia: 200px
   - Raias começam em X=50, width=2000px

2. COORDENADAS DOS ELEMENTOS
   - Evento Início: X=100, Y=(raia_center), width=40, height=40
   - Atividades: width=120, height=80
   - Gateway: width=50, height=50
   - Evento Fim: width=40, height=40
   - Espaçamento horizontal entre elementos: 280px
   - Centro Y de cada raia: raia_Y + 100

3. FLUXO DE SEQUÊNCIA
   - Mapeia sequência exata: evento_inicio → atividade1 → atividade2 → ... → evento_fim
   - Se houver decisão (gateway): identifique os fluxos "Sim" e "Não"
   - Se houver ramificações paralelas: documente claramente
   - Se houver transição entre raias: marque como "inter_lane_transition": true

4. WAYPOINTS PARA SETAS
   - Waypoint inicial: borda direita do elemento de origem
     origem_x + origem_width/2, origem_y
   - Waypoint final: borda esquerda do elemento de destino
     destino_x - destino_width/2, destino_y
   - Se passar por outra raia: adicione waypoints intermediários
     Exemplo: seta sai de raia 1, passa por raia 2, entra em raia 3
     Waypoints: [(start_x, start_y), (intermediário_x, raia2_center), (end_x, end_y)]

5. SINCRONIZAÇÕES
   - Se duas atividades precisam sincronizar: marque com "synchronization_point": true
   - Indique qual atividade aguarda qual: "waits_for": "activity_id"

6. RESPONSÁVEIS
   - Cada atividade DEVE ter um responsável explícito
   - Se não houver no JSON: use "Responsável não identificado"
   - Mapeia automaticamente para a raia correta

7. GATEWAYS E DECISÕES (REGRA CRÍTICA)

   - TODA condição DEVE ser convertida em uma PERGUNTA explícita
     Exemplo:
       "há validação" → "A validação foi realizada?"
       "verificar documento" → "O documento está válido?"

   - O nome do gateway DEVE sempre terminar com "?"
   - Nunca use frases descritivas, apenas perguntas claras e objetivas

   - TODO gateway DEVE obrigatoriamente ter EXATAMENTE 2 saídas:
       1. "Sim"
       2. "Não"

   - PADRÃO VISUAL DAS SETAS:
       - "Sim" → sai pela BORDA DIREITA do gateway
       - "Não" → sai pela BORDA ESQUERDA do gateway

   - POSICIONAMENTO DAS SETAS:
       - Ambas devem sair CENTRALIZADAS verticalmente no gateway
       - Coordenada Y = centro do gateway (gateway_y)

   - WAYPOINTS OBRIGATÓRIOS:
       Para "Sim":
         ponto inicial = (gateway_x + width/2, gateway_center_y)

       Para "Não":
         ponto inicial = (gateway_x - width/2, gateway_center_y)

   - FLUXO PADRÃO (default_flow):
       - Sempre deve ser "Sim", exceto quando explicitamente indicado

   - É PROIBIDO:
       - Gateway com apenas uma saída
       - Gateway com mais de duas saídas
       - Labels diferentes de "Sim" e "Não"
       - Setas saindo por cima ou por baixo do gateway

   - ESTRUTURA OBRIGATÓRIA:
     "outgoing": [
       {
         "id": "flow_sim",
         "label": "Sim",
         "target": "activity_X"
       },
       {
         "id": "flow_nao",
         "label": "Não",
         "target": "activity_Y"
       }
     ]
      REGRA ESPECIAL PARA GATEWAYS:
   - Nunca conecte diretamente atividade → atividade passando "por dentro" do gateway
   - Sempre:
       origem → gateway → destino

   - Para saída "Sim" (direita):
       [
         (gateway_right_x, center_y),
         (gateway_right_x + 80, center_y),
         (... até destino)
       ]

   - Para saída "Não" (esquerda):
       [
         (gateway_left_x, center_y),
         (gateway_left_x - 80, center_y),
         (... até destino)
       ]

8. OBJETOS DE DADOS E DOCUMENTOS
   - Inclua documentos mencionados
   - Posicione perto das atividades que os usam
   - Tipo: "dataObject" ou "dataStore"

9. MARCOS (MILESTONES)
   - Indique marcos importantes do processo
   - Não a cada 3 atividades: apenas marcos realmente significativos
   - Exemplo: "Sinistro documentado", "Responsável identificado"

FORMATO DO JSON DE SAÍDA:

json
{
  "metadata": {
    "processo": "string",
    "versao": "YYYYMMDD-01",
    "descricao": "string",
    "autor": "string",
    "unidade": "string"
  },

  "lanes": [
    {
      "id": "lane_0",
      "nome": "string (nome do ator)",
      "index": 0,
      "y": 50,
      "x": 50,
      "width": 2000,
      "height": 200,
      "center_y": 150
    }
  ],

  "events": [
    {
      "id": "event_start",
      "nome": "Processo iniciado",
      "tipo": "start",
      "lane_id": "lane_0",
      "x": 100,
      "y": 150,
      "width": 40,
      "height": 40,
      "outgoing": ["flow_0"]
    }
  ],

  "activities": [
    {
      "id": "activity_0",
      "nome": "string (verbo infinitivo)",
      "tipo": "manual|user|service|send|receive|script",
      "responsavel": "string",
      "lane_id": "lane_X",
      "x": 280,
      "y": 150,
      "width": 120,
      "height": 80,
      "incoming": ["flow_0"],
      "outgoing": ["flow_1"],
      "documentos": ["doc1", "doc2"],
      "descricao": "string"
    }
  ],

  "gateways": [
    {
      "id": "gateway_0",
      "nome": "Pergunta ou condição?",
      "tipo": "exclusive",
      "lane_id": "lane_X",
      "x": 640,
      "y": 150,
      "width": 50,
      "height": 50,
      "incoming": ["flow_1"],
      "outgoing": [
        {
          "id": "flow_sim",
          "label": "Sim",
          "target": "activity_2"
        },
        {
          "id": "flow_nao",
          "label": "Não",
          "target": "activity_3"
        }
      ],
      "default_flow": "flow_sim"
    }
  ],

  "sequence_flows": [
    {
      "id": "flow_0",
      "source": "event_start",
      "target": "activity_0",
      "label": "",
      "waypoints": [
        { "x": 140, "y": 150 },
        { "x": 220, "y": 150 }
      ],
      "inter_lane_transition": false,
      "passes_through_lanes": []
    },
    {
      "id": "flow_inter_lanes",
      "source": "activity_0",
      "target": "activity_1",
      "label": "",
      "waypoints": [
        { "x": 400, "y": 150 },
        { "x": 520, "y": 150 },
        { "x": 520, "y": 250 },
        { "x": 280, "y": 250 }
      ],
      "inter_lane_transition": true,
      "passes_through_lanes": ["lane_0", "lane_1"]
    }
  ],

  "data_objects": [
    {
      "id": "dataObject_0",
      "nome": "nome do documento",
      "tipo": "dataObject",
      "x": 400,
      "y": 250,
      "width": 60,
      "height": 60
    }
  ],

  "milestones": [
    {
      "id": "milestone_0",
      "nome": "Milestone importante",
      "linked_activity": "activity_X"
    }
  ],

  "synchronizations": [
    {
      "id": "sync_0",
      "activity_a": "activity_0",
      "activity_b": "activity_1",
      "tipo": "join|fork|both",
      "descricao": "Descrição da sincronização"
    }
  ]
}


ANÁLISE E CONVERSÃO:

1. Leia o JSON de DPT fornecido
2. Identifique:
   - Atores (para raias)
   - Sequência de atividades
   - Decisões/gateways
   - Transições entre raias
   - Documentos/objetos de dados
   - Marcos importantes
3. Calcule coordenadas para cada elemento
4. Defina waypoints para cada fluxo
5. Marque transições inter-raias
6. Retorne EXCLUSIVAMENTE o JSON (sem texto antes ou depois)



---

IMPORTANTE:
- Retorne APENAS o JSON, válido e bem formatado
- Sem comentários, sem markdown, sem texto adicional
- JSON deve começar com { e terminar com }
- Coordenadas em pixels (valores inteiros)
- Todas as referências de IDs devem existir (sem IDs órfãos)
- Waypoints devem refletir a real trajetória das setas
```

---



## 📊 Exemplo de Entrada (JSON DPT)


{
  "metadados": {
    "nome_processo": "Processamento do Sinistro",
    "nome_unidade": "COTRANS",
    "elaborado_por": "Isabella Cristina"
  },
  "atores": {
    "lista": ["Motorista", "Setor Sinistros", "Oficina"]
  },
  "principais_etapas": [
    {
      "ordem": 1,
      "etapa": "Documentar danos",
      "responsavel": "Motorista"
    },
    {
      "ordem": 2,
      "etapa": "Criar processo no SEI",
      "responsavel": "Setor Sinistros",
      "condicoes": "Há clareza sobre responsável?"
    },
    {
      "ordem": 3,
      "etapa": "Analisar danos",
      "responsavel": "Oficina"
    }
  ],
  "documentos_e_indicadores": {
    "documentos": {
      "lista": ["Boletim de Ocorrência", "Fotos", "Recibo"]
    }
  }
}


---

## 📊 Exemplo de Saída (JSON BPMN Otimizado)

json
{
  "metadata": {
    "processo": "Processamento do Sinistro",
    "versao": "20251117-01",
    "descricao": "O modelo de processo atual (As Is) descreve...",
    "autor": "Isabella Cristina",
    "unidade": "COTRANS"
  },

  "lanes": [
    {
      "id": "lane_0",
      "nome": "Motorista",
      "index": 0,
      "y": 50,
      "x": 50,
      "width": 2000,
      "height": 200,
      "center_y": 150
    },
    {
      "id": "lane_1",
      "nome": "Setor Sinistros",
      "index": 1,
      "y": 250,
      "x": 50,
      "width": 2000,
      "height": 200,
      "center_y": 350
    },
    {
      "id": "lane_2",
      "nome": "Oficina",
      "index": 2,
      "y": 450,
      "x": 50,
      "width": 2000,
      "height": 200,
      "center_y": 550
    }
  ],

  "events": [
    {
      "id": "event_start",
      "nome": "Sinistro reportado",
      "tipo": "start",
      "lane_id": "lane_0",
      "x": 100,
      "y": 150,
      "width": 40,
      "height": 40,
      "outgoing": ["flow_0"]
    },
    {
      "id": "event_end",
      "nome": "Sinistro processado",
      "tipo": "end",
      "lane_id": "lane_2",
      "x": 1200,
      "y": 550,
      "width": 40,
      "height": 40,
      "incoming": ["flow_3"]
    }
  ],

  "activities": [
    {
      "id": "activity_0",
      "nome": "Documentar danos",
      "tipo": "manual",
      "responsavel": "Motorista",
      "lane_id": "lane_0",
      "x": 280,
      "y": 110,
      "width": 120,
      "height": 80,
      "incoming": ["flow_0"],
      "outgoing": ["flow_1"],
      "documentos": ["Fotos"],
      "descricao": "Tirar fotos e vídeos dos danos"
    },
    {
      "id": "activity_1",
      "nome": "Criar processo no SEI",
      "tipo": "user",
      "responsavel": "Setor Sinistros",
      "lane_id": "lane_1",
      "x": 560,
      "y": 310,
      "width": 120,
      "height": 80,
      "incoming": ["flow_1"],
      "outgoing": ["flow_2"],
      "documentos": ["Boletim de Ocorrência"],
      "descricao": "Abrir processo de manutenção de veículo"
    },
    {
      "id": "activity_2",
      "nome": "Analisar danos",
      "tipo": "service",
      "responsavel": "Oficina",
      "lane_id": "lane_2",
      "x": 840,
      "y": 510,
      "width": 120,
      "height": 80,
      "incoming": ["flow_2"],
      "outgoing": ["flow_3"],
      "documentos": ["Fotos", "Recibo"],
      "descricao": "Avaliar danos e fazer orçamento"
    }
  ],

  "gateways": [
    {
      "id": "gateway_0",
      "nome": "Há clareza sobre responsável?",
      "tipo": "exclusive",
      "lane_id": "lane_1",
      "x": 700,
      "y": 310,
      "width": 50,
      "height": 50,
      "incoming": ["flow_1"],
      "outgoing": [
        {
          "id": "flow_sim",
          "label": "Sim",
          "target": "activity_2"
        },
        {
          "id": "flow_nao",
          "label": "Não",
          "target": "activity_investigar"
        }
      ],
      "default_flow": "flow_sim"
    }
  ],

  "sequence_flows": [
    {
      "id": "flow_0",
      "source": "event_start",
      "target": "activity_0",
      "label": "",
      "waypoints": [
        { "x": 140, "y": 150 },
        { "x": 220, "y": 150 }
      ],
      "inter_lane_transition": false,
      "passes_through_lanes": []
    },
    {
      "id": "flow_1",
      "source": "activity_0",
      "target": "activity_1",
      "label": "",
      "waypoints": [
        { "x": 400, "y": 150 },
        { "x": 480, "y": 150 },
        { "x": 480, "y": 350 },
        { "x": 560, "y": 350 }
      ],
      "inter_lane_transition": true,
      "passes_through_lanes": ["lane_0", "lane_1"]
    },
    {
      "id": "flow_2",
      "source": "activity_1",
      "target": "activity_2",
      "label": "",
      "waypoints": [
        { "x": 680, "y": 350 },
        { "x": 760, "y": 350 },
        { "x": 760, "y": 550 },
        { "x": 840, "y": 550 }
      ],
      "inter_lane_transition": true,
      "passes_through_lanes": ["lane_1", "lane_2"]
    },
    {
      "id": "flow_3",
      "source": "activity_2",
      "target": "event_end",
      "label": "",
      "waypoints": [
        { "x": 960, "y": 550 },
        { "x": 1100, "y": 550 }
      ],
      "inter_lane_transition": false,
      "passes_through_lanes": []
    }
  ],

  "data_objects": [
    {
      "id": "dataObject_0",
      "nome": "Boletim de Ocorrência",
      "tipo": "dataObject",
      "x": 560,
      "y": 450,
      "width": 60,
      "height": 60
    },
    {
      "id": "dataObject_1",
      "nome": "Fotos dos Danos",
      "tipo": "dataObject",
      "x": 280,
      "y": 220,
      "width": 60,
      "height": 60
    }
  ],

  "milestones": [
    {
      "id": "milestone_0",
      "nome": "Danos documentados",
      "linked_activity": "activity_0"
    },
    {
      "id": "milestone_1",
      "nome": "Processo criado no SEI",
      "linked_activity": "activity_1"
    }
  ],

  "synchronizations": []
}


---

## 🔍 Detalhes Importantes

### Waypoints


Simples (mesma raia):
  "waypoints": [
    { "x": 400, "y": 150 },  ← fim do elemento anterior
    { "x": 480, "y": 150 }   ← início do elemento posterior
  ]

Inter-raias (passa por raias diferentes):
  "waypoints": [
    { "x": 400, "y": 150 },  ← fim de activity_0 (raia_0)
    { "x": 480, "y": 150 },  ← meio horizontal
    { "x": 480, "y": 350 },  ← passa pela raia_1 (centro_y=350)
    { "x": 560, "y": 350 }   ← início de activity_1 (raia_1)
  ]

Com Gateway:
  Parte do elemento anterior, passa pelo gateway, 
  e segue para elemento posterior (sim ou não)


### Identificação de Tipos de Tarefas


"manual"      ← Padrão, trabalho manual
"user"        ← Interação com usuário (preencher, clicar)
"service"     ← Integração com sistema
"send"        ← Envio de mensagem/documento
"receive"     ← Recepção de mensagem/documento
"script"      ← Automação/script
```

---

## 💡 Dicas

1. **Sempre use este prompt** antes de gerar BPMN
2. **Verifique os waypoints** - eles definem a trajetória das setas
3. **Transições inter-raias** precisam de waypoints que passem pelo centro Y das raias intermediárias
4. **Coordenadas em pixels** - quanto maior X, mais para a direita
5. **Índice de raia** define a ordem de cima para baixo

---

"""


_STEP2_XML_PROMPT = """Converta o JSON abaixo em código XML BPMN 2.0 válido.

--- ESTRUTURA JSON ---
{structure_json}
--- FIM ---

REGRAS OBRIGATÓRIAS:
1. **Cabeçalho obrigatório**: O elemento <bpmn:process> DEVE conter:
   - Atributo name com o nome do processo (ex: name="Processamento de sinistro")
   - Um elemento <bpmn:documentation> como PRIMEIRO filho do <bpmn:process> com o seguinte conteúdo EXATO:
     Autor: [valor do campo author do JSON] - CEPROC
     Versão: {version}
     Descrição: [valor do campo documentation do JSON]
   - A Versão DEVE estar no formato YYYYMMDD-01 conforme padrão COGEPRO (ex: 20251117-01).
     NÃO altere o valor da versão fornecido acima.
2. **Estrutura XML**:
   - <bpmn:definitions> como raiz com namespaces corretos
   - <bpmn:collaboration> com <bpmn:participant> referenciando o processo. O <bpmn:participant> DEVE ter atributo name com o nome do processo.
   - <bpmn:process> com <bpmn:laneSet> contendo as lanes
   - Cada lane com <bpmn:flowNodeRef> listando seus elementos
   - Todos os elementos (startEvent, task, exclusiveGateway, intermediateThrowEvent, endEvent)
   - Todos os sequenceFlow com sourceRef e targetRef corretos
3. **Namespaces obrigatórios**:
   - xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
   - xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
   - xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
   - xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
4. **Marcos (Milestones)**: Elementos do tipo "intermediateThrowEvent" representam marcos do processo. Gere-os como <bpmn:intermediateThrowEvent> no XML.
5. **NÃO inclua** <bpmndi:BPMNDiagram> — o layout será calculado automaticamente.

OUTPUT: Gere APENAS o XML válido. Comece com <?xml e termine com </bpmn:definitions>."""


async def modulo_2_bpmn_as_is(relatorio_descoberta: str) -> str:
    """Chain-of-thought: extrai estrutura → gera XML → auto-layout."""
    client = get_client()
    version = _get_version_as_is()

    # Passo 1: Extrair estrutura como JSON
    prompt_1 = _STEP1_STRUCTURE_PROMPT.format(relatorio=relatorio_descoberta)
    structure_json = _chat(client, SYSTEM_PROMPT, prompt_1)
    
    # Limpar JSON de possíveis marcadores de código
    structure_json = structure_json.strip()
    if structure_json.startswith("```"):
        structure_json = re.sub(r'^```(?:json)?\s*\n?', '', structure_json)
        structure_json = re.sub(r'\n?\s*```$', '', structure_json)

    # Passo 2: Gerar XML BPMN a partir do JSON
    prompt_2 = _STEP2_XML_PROMPT.format(
        structure_json=structure_json,
        version=version
    )
    xml_result = _chat(client, SYSTEM_PROMPT, prompt_2)
    
    # Limpar XML de possíveis marcadores de código
    xml_text = xml_result.strip()
    if xml_text.startswith("```"):
        xml_text = re.sub(r'^```(?:xml)?\s*\n?', '', xml_text)
        xml_text = re.sub(r'\n?\s*```$', '', xml_text)

    # Passo 3: Auto-layout com Python (coordenadas calculadas)
    from bpmn_generator import auto_layout_bpmn
    xml_text = auto_layout_bpmn(xml_text)

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

Numere cada proposta de melhoria para que o usuário possa selecionar quais aprovar.
Apresente de forma clara e profissional em Markdown."""

    return _chat(client, SYSTEM_PROMPT, prompt)


# ═══════════════════════════════════════════════════════════════════
# MÓDULO 3B: REDESENHO TO-BE (Chain-of-Thought)
# ═══════════════════════════════════════════════════════════════════

_STEP1_TOBE_PROMPT = """Com base no relatório, consultoria e propostas APROVADAS, extraia a ESTRUTURA do processo TO-BE (otimizado) em formato JSON.

--- RELATÓRIO DE DESCOBERTA ---
{relatorio}
--- FIM ---

--- CONSULTORIA E SUGESTÕES ---
{consultoria}
--- FIM ---

--- PROPOSTAS APROVADAS ---
{propostas}
--- FIM ---

Retorne APENAS um JSON válido com esta estrutura:

{{
  "process_name": "Nome do processo otimizado",
  "author": "CEPROC",
  "documentation": "O modelo de processo revisado (To Be) descreve [completar com o objetivo do processo otimizado, descrevendo as melhorias incorporadas]",
  "lanes": [
    {{"id": "lane_1", "name": "Nome do Ator/Setor"}}
  ],
  "elements": [
    {{"id": "start_1", "type": "startEvent", "name": "Início", "lane": "lane_1"}},
    {{"id": "task_1", "type": "task", "name": "Verbo no Infinitivo + Complemento", "lane": "lane_1"}},
    {{"id": "gw_1", "type": "exclusiveGateway", "name": "Pergunta de decisão?", "lane": "lane_1"}},
    {{"id": "milestone_1", "type": "intermediateThrowEvent", "name": "Nome do Marco", "lane": "lane_1"}},
    {{"id": "end_1", "type": "endEvent", "name": "Fim", "lane": "lane_1"}}
  ],
  "flows": [
    {{"id": "flow_1", "from": "start_1", "to": "task_1", "label": ""}}
  ]
}}

REGRAS:
1. INCORPORE todas as melhorias/propostas aprovadas no novo fluxo
2. Tarefas DEVEM usar verbos no INFINITIVO (ex: "Receber", "Analisar", "Encaminhar")
3. Gateways DEVEM ser formulados como PERGUNTAS (ex: "Documento correto?", "Prazo expirado?")
4. IDs únicos, sem espaços (use underscore)
5. Flows conectando todos os elementos logicamente
6. Use "intermediateThrowEvent" para marcar MARCOS importantes do processo (conclusão de fases, entregas, mudanças de responsabilidade). Inclua pelo menos 1 marco.
7. O campo "documentation" DEVE começar com "O modelo de processo revisado (To Be) descreve" seguido de uma descrição do processo otimizado
8. O processo DEVE ter exatamente 1 evento de início e pelo menos 1 evento de fim
9. Todas as lanes DEVEM representar atores ou setores reais
10. NÃO usar subprocessos — manter todas as atividades no nível principal
11. Retorne APENAS o JSON"""


async def modulo_3b_redesenho_to_be(
    relatorio_descoberta: str,
    consultoria: str,
    propostas_aprovadas: str
) -> str:
    """Chain-of-thought: extrai estrutura TO-BE → gera XML → auto-layout."""
    client = get_client()
    version = _get_version_to_be()

    # Passo 1: Extrair estrutura TO-BE como JSON
    prompt_1 = _STEP1_TOBE_PROMPT.format(
        relatorio=relatorio_descoberta,
        consultoria=consultoria,
        propostas=propostas_aprovadas
    )
    structure_json = _chat(client, SYSTEM_PROMPT, prompt_1)
    
    structure_json = structure_json.strip()
    if structure_json.startswith("```"):
        structure_json = re.sub(r'^```(?:json)?\s*\n?', '', structure_json)
        structure_json = re.sub(r'\n?\s*```$', '', structure_json)

    # Passo 2: Gerar XML BPMN
    prompt_2 = _STEP2_XML_PROMPT.format(
        structure_json=structure_json,
        version=version
    )
    xml_result = _chat(client, SYSTEM_PROMPT, prompt_2)
    
    xml_text = xml_result.strip()
    if xml_text.startswith("```"):
        xml_text = re.sub(r'^```(?:xml)?\s*\n?', '', xml_text)
        xml_text = re.sub(r'\n?\s*```$', '', xml_text)

    # Passo 3: Auto-layout
    from bpmn_generator import auto_layout_bpmn
    xml_text = auto_layout_bpmn(xml_text)

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

---
*Documento gerado pelo Mapeador Inteligente — CEPROC/TJMG*

Gere o POP completo em Markdown, de forma clara, didática e profissional."""

    return _chat(client, SYSTEM_PROMPT, prompt)
