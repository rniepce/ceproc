# Documentação Técnica - CEPROC

## 1. Visão Geral

O CEPROC (Chat-Enabled Process Creator) é um sistema projetado para transformar descrições de processos de negócios, fornecidas em linguagem natural, em artefatos técnicos estruturados. O sistema utiliza a inteligência artificial do Google Gemini para interpretar a entrada do usuário e gerar:

1.  Um mapeamento de processo detalhado em formato JSON.
2.  Um diagrama de processo no padrão BPMN 2.0 (Business Process Model and Notation).
3.  Um documento PDF contendo as informações do processo e o diagrama.

O objetivo de negócio é agilizar e democratizar a modelagem de processos, permitindo que usuários de negócio possam criar documentação e diagramas formais sem a necessidade de conhecimento técnico em BPMN ou ferramentas complexas.

## 2. Stack Tecnológica

O sistema é dividido em duas partes principais: um backend em Python e um frontend em JavaScript puro, CSS e HTML.

| Componente | Tecnologia | Biblioteca/Framework | Propósito no Sistema |
| :--- | :--- | :--- | :--- |
| **Backend** | Python | **FastAPI** | Criação de uma API web de alta performance para receber as requisições do frontend. |
| | | **Uvicorn** | Servidor ASGI para rodar a aplicação FastAPI. |
| | | **Google Gemini (google-generativeai)** | É o cérebro do sistema, responsável por interpretar a linguagem natural e gerar a estrutura do processo. |
| | | **ReportLab** | Utilizada para a geração dinâmica do documento de processo em formato PDF. |
| | | **xml.etree.ElementTree** | Manipulação e geração do arquivo XML para o diagrama BPMN. |
| **Frontend**| JavaScript | N/A (Vanilla JS) | Orquestra a interação do usuário, envia as requisições para o backend e renderiza os resultados. |
| | CSS | N/A (Vanilla CSS) | Estilização da interface de usuário, focada em simplicidade e usabilidade. |
| | HTML | N/A | Estrutura a página web e os elementos com os quais o usuário interage. |
| **Container** | Docker | **Dockerfile** | Define o ambiente e as dependências para containerizar e facilitar o deploy da aplicação. |

## 3. Arquitetura

A arquitetura do CEPROC é um **Monolito com separação de camadas (Client-Server)**.

-   **Frontend (Cliente):** Uma aplicação de página única (SPA) simples, construída com HTML, CSS e JavaScript. É responsável por capturar a entrada do usuário e se comunicar com o backend via requisições HTTP.
-   **Backend (Servidor):** Uma API RESTful construída com FastAPI. Esta API expõe endpoints que recebem a descrição do processo, orquestram a lógica de negócio (interação com o Gemini, geração de BPMN e PDF) e retornam os artefatos gerados.
-   **Containerização:** O `Dockerfile` presente na raiz do projeto indica a intenção de empacotar a aplicação (backend e frontend) em um contêiner Docker, o que padroniza o ambiente de execução e simplifica o deploy.

Esta arquitetura é adequada para o escopo do projeto, sendo simples de desenvolver, testar e implantar.

## 4. Fluxo de Dados/Processos

O fluxo crítico do sistema começa na interface do usuário e termina com a entrega dos artefatos do processo.

1.  **Entrada do Usuário:** O usuário insere a descrição de um processo de negócio no campo de texto da interface web e clica em "Gerar Processo".
2.  **Requisição Frontend -> Backend:** O JavaScript do frontend captura o texto e envia uma requisição `POST` para o endpoint `/generate_process` da API no backend.
3.  **Orquestração no Backend (`main.py`):**
    a. O endpoint recebe a requisição.
    b. A função chama o módulo `gemini_engine.py`, passando a descrição do processo.
4.  **Processamento com IA (`gemini_engine.py`):**
    a. O `gemini_engine` formata a entrada do usuário em um prompt estruturado, instruindo a IA a gerar um JSON com os detalhes do processo (nome, objetivo, etapas, etc.).
    b. O prompt é enviado para a API do Google Gemini.
    c. O motor recebe a resposta (o JSON gerado pela IA) e a retorna para o `main.py`.
5.  **Geração de Artefatos (`main.py`):**
    a. **Geração de BPMN:** O `main.py` invoca o `bpmn_generator.py`, passando o JSON do processo. Este módulo constrói uma estrutura XML correspondente ao diagrama BPMN e a salva em um arquivo.
    b. **Geração de PDF:** Em seguida, o `main.py` chama o `pdf_generator.py`, que usa o mesmo JSON para criar um documento PDF estilizado com os detalhes do processo.
6.  **Resposta Backend -> Frontend:** A API retorna uma resposta JSON para o frontend, contendo os links para download do arquivo BPMN e do PDF gerados.
7.  **Exibição no Frontend:** O JavaScript interpreta a resposta e exibe na tela os links para que o usuário possa baixar os artefatos.

## 5. Guia de Setup

Siga estes passos para configurar e executar o projeto em um ambiente local.

### Pré-requisitos

-   Python 3.8+
-   Docker (recomendado, para seguir o `Dockerfile`)
-   Uma chave de API do **Google Gemini**.

### Passos

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/rniepce/ceproc.git
    cd ceproc
    ```

2.  **Configuração do Backend:**
    a. Navegue até a pasta `backend`:
       ```bash
       cd backend
       ```
    b. Crie e ative um ambiente virtual (recomendado):
       ```bash
       python -m venv venv
       source venv/bin/activate  # No Windows: venv\Scripts\activate
       ```
    c. Instale as dependências:
       ```bash
       pip install -r requirements.txt
       ```
    d. Configure as variáveis de ambiente. Renomeie o arquivo `.env.example` para `.env` e adicione sua chave da API do Gemini:
       ```
       # backend/.env
       GEMINI_API_KEY="SUA_CHAVE_DE_API_AQUI"
       ```

3.  **Execução:**
    a. A partir da pasta `backend`, inicie o servidor com Uvicorn:
       ```bash
       uvicorn main:app --reload
       ```
       O servidor estará rodando em `http://127.0.0.1:8000`.

4.  **Acesso ao Frontend:**
    a. Abra o arquivo `frontend/index.html` diretamente no seu navegador.
    b. A aplicação já está configurada para fazer requisições para `http://127.0.0.1:8000`.

## 6. Principais Módulos/Classes

A estrutura do projeto é direta e funcional, com responsabilidades bem definidas.

### Backend

| Arquivo/Módulo | Responsabilidade |
| :--- | :--- |
| **`main.py`** | **Orquestrador e Ponto de Entrada da API.** Define os endpoints da API com FastAPI, recebe as requisições do frontend e coordena a chamada aos outros módulos (`gemini_engine`, `bpmn_generator`, `pdf_generator`) para executar o fluxo principal. |
| **`gemini_engine.py`** | **Motor de Inteligência Artificial.** Contém toda a lógica para se comunicar com a API do Google Gemini. É responsável por construir os prompts, enviar as requisições para a IA e processar as respostas (JSON). |
| **`bpmn_generator.py`** | **Gerador de BPMN.** Recebe o JSON estruturado do processo e o utiliza para construir um arquivo XML válido no formato BPMN 2.0. Utiliza a biblioteca `xml.etree.ElementTree` para criar a estrutura do diagrama. |
| **`pdf_generator.py`** | **Gerador de PDF.** Usa a biblioteca ReportLab para criar um documento PDF a partir do JSON do processo. Formata os dados do processo de maneira legível e profissional. |
| **`requirements.txt`**| **Gerenciador de Dependências.** Lista todas as bibliotecas Python necessárias para que o backend funcione corretamente. |

### Frontend

| Arquivo/Módulo | Responsabilidade |
| :--- | :--- |
| **`index.html`** | **Estrutura da Página.** Define a estrutura semântica da interface do usuário, incluindo o formulário de entrada, botões e a área onde os resultados são exibidos. |
| **`css/style.css`** | **Estilização Visual.** Contém todas as regras de CSS para dar à aplicação sua aparência, incluindo layout, cores, fontes e responsividade básica. |
| **`js/script.js`** | **Lógica de Interação.** Manipula os eventos do usuário (clique no botão), envia a requisição `fetch` para o backend com os dados do formulário, processa a resposta e atualiza o DOM para exibir os links de download. |

## 7. Pontos de Atenção e Recomendações

-   **Dívida Técnica (Baixa):** O acoplamento entre o `main.py` e os geradores (`bpmn_generator`, `pdf_generator`) é funcional, mas poderia ser abstraído. A introdução de classes (`ProcessGenerator`, por exemplo) ou um padrão de design como o *Strategy* poderia tornar o código mais extensível se novos formatos de saída forem necessários no futuro (ex: PNG, SVG).
-   **Recomendação de Melhoria:** A interface de usuário (frontend) é servida de forma estática (abrindo o HTML). Uma melhoria seria fazer com que a própria aplicação FastAPI sirva os arquivos estáticos do frontend. Isso unificaria a aplicação sob um único servidor e facilitaria o deploy.
-   **Segurança:** A chave da API do Gemini é lida de um arquivo `.env`. É crucial garantir que este arquivo nunca seja versionado no Git. O `.gitignore` na raiz do projeto já previne isso, mas é um ponto de atenção importante.
-   **UX (User Experience):** O feedback para o usuário durante o processamento (que pode levar alguns segundos) é limitado. A implementação de um *spinner* ou indicador de carregamento no frontend melhoraria significativamente a experiência do usuário.
