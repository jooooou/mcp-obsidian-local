# 🧠 Local Obsidian AI Agent (MVP)

Este projeto implementa um **Agente de IA totalmente local** capaz de interagir com seu cofre (Vault) do Obsidian. Ele utiliza um modelo LLM rodando via `llama.cpp` para raciocinar (ReAct) e um servidor MCP (FastAPI) para executar ações reais nas suas notas.

> **⚠️ STATUS DO PROJETO: Alpha / Versão Básica**
> Este é um MVP (Mínimo Produto Viável).
> **Features:** Agente ReAct, Ferramentas de Leitura/Escrita no Obsidian.
> **Stack:** Python, uv, Llama.cpp (GPU), FastAPI.

## 📋 Pré-requisitos

1.  **Gerenciador de Pacotes `uv`**: [Instalar uv](https://github.com/astral-sh/uv).
2.  **Obsidian**: Com o plugin **Local REST API** instalado e ativo.
3.  **Hardware**: Recomendado **GPU NVIDIA** (Drivers e CUDA Toolkit instalados).
4.  **Make**: Ferramenta de build (padrão no Linux/WSL. No Windows, use WSL ou instale via chocolatey).
5.  **Modelo GGUF**: Um modelo `.gguf` (Recomendado: *Qwen 2.5* ou *Llama 3.1* Instruct).

---

## 🛠️ Instalação Simplificada

### 1. Configurar o Obsidian
1.  No Obsidian, vá em **Settings > Community Plugins > Browse**.
2.  Instale o plugin **Local REST API**.
3.  Habilite o plugin e copie o **API Key** (Token).

### 2. Configurar o Projeto
Este projeto usa um `Makefile` para garantir que o suporte a GPU seja compilado corretamente.

1.  Clone este repositório.
2.  Execute a instalação:

    ```bash
    make install
    ```
    *Isso vai criar o ambiente virtual, baixar as libs e compilar o llama.cpp usando sua placa de vídeo.*

### 3. Configurar Variáveis (.env)
Crie um arquivo `.env` na raiz:

```ini
# Obsidian Config (Local REST API)
OBSIDIAN_API_URL=[http://127.0.0.1:27123](http://127.0.0.1:27123)
OBSIDIAN_API_TOKEN=seu_token_aqui

# Caminho absoluto para seu modelo .gguf
MODEL_PATH=/home/usuario/ai/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf

# Servidor MCP (Padrão)
MCP_URL=http://localhost:8080/tools/call
````

-----

## 🚀 Como Usar

Abra dois terminais na pasta do projeto.

**Terminal 1: Iniciar o Servidor**

```bash
make server
```

**Terminal 2: Iniciar o Agente**

```bash
make agent
```

**Exemplo de interação:**

> **Você:** "Verifique se tenho alguma nota sobre 'Receitas' e, se não tiver, crie uma com uma lista de ingredientes para bolo."
>
> **Agente:** (O agente vai buscar, não encontrar, e então criar a nota).

-----

## 📦 Gestão de Dependências

Se precisar adicionar novas bibliotecas (ex: numpy), use:

```bash
uv add numpy
```

*Nota: O `llama-cpp-python` não deve ser atualizado via `uv sync` puro para não perder o suporte a GPU. Se precisar reinstalá-lo, rode `make install` novamente.*

-----

## 🗺️ Roadmap

  - [ ] **RAG (Memória):** Ler notas antigas para contexto.
  - [ ] **Multi-Agentes:** Especialistas em tarefas distintas (escrita, organização, etc..)
  - [ ] **Prompt Template:** Melhorar o System Prompt para evitar alucinações de JSON.
  - [] **Criação de Tools** Capacidade de criar novas tools.
  - [] **Interface de configuração** Jeito fácil de trocar prompts e modelos.

-----

## 🆘 Troubleshooting

  * **Erro `make: command not found`**: Instale o pacote `build-essential` (Ubuntu/Debian) ou use WSL no Windows.
  * **Lentidão Extrema**: Verifique se o modelo foi carregado na GPU olhando os logs do `make agent`. Se aparecer `BLAS = 0`, rode `make install` novamente.