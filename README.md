# 🧠 Local Obsidian AI Agent (Skills-Based)

Este projeto implementa um **Agente de IA local autônomo** projetado para ser seu assistente pessoal dentro do Obsidian. Diferente de bots tradicionais, este agente utiliza uma arquitetura baseada em **Habilidades (Skills)**, inspirada em frameworks modernos como OpenClaw e Claude Code.

O agente é capaz de ler suas notas, criar conteúdo, realizar buscas profundas no seu sistema de arquivos e executar comandos do Obsidian, tudo de forma local e privada.

---

## 🏗️ Arquitetura do Sistema

A arquitetura é dividida em dois componentes principais que trabalham em conjunto através de um loop de raciocínio (ReAct):

### 1. O Núcleo do Agente (`agent.py`)
O "cérebro" do sistema. Ele gerencia o modelo de linguagem (LLM) e a interface de execução.
- **LLM Engine:** Utiliza `llama.cpp` para rodar modelos GGUF com aceleração de GPU.
- **Programmatic Tool Calling:** O agente possui ferramentas "nativas" escritas em Python que ele pode invocar via JSON estruturado:
    - `list_skills`: Lista os manuais de instruções disponíveis.
    - `load_skill`: Carrega o manual de uma habilidade específica para o contexto da conversa.
    - `execute_shell`: Permite ao agente rodar comandos Bash (como `curl`, `grep`, `ls`).
    - `read_file`: Lê arquivos diretamente do disco.
- **Context Management:** Monitora o uso de tokens e gerencia o histórico da conversa para manter o agente focado e dentro dos limites de memória do modelo.

### 2. Sistema de Skills (`skills/`)
As funcionalidades não são "hardcoded" no Python. Em vez disso, elas são definidas em arquivos Markdown (`SKILL.md`).
- **Aprendizado Dinâmico:** O agente começa "limpo". Ao encontrar um problema, ele descobre que existe uma skill (ex: `obsidian`), lê o manual e aprende instantaneamente como usar ferramentas CLI (como `curl` contra a API do Obsidian) para resolver o pedido.
- **Flexibilidade:** Adicionar novas capacidades (ex: integração com Git, Python REPL, Dataview) é tão simples quanto criar uma nova pasta com um arquivo Markdown explicativo.

---

## 🛠️ Como as Ferramentas Funcionam

### Fluxo de Execução (Loop ReAct)
1.  **Pensamento (`<thought>`):** O modelo analisa o pedido do usuário e decide qual ferramenta ou skill é necessária.
2.  **Chamada de Ferramenta (`<tool_call>`):** O modelo gera um JSON descrevendo a ação (ex: chamar `execute_shell` com um comando `curl`).
3.  **Execução:** O `agent.py` intercepta esse JSON, executa o código Python ou o comando no terminal e captura o resultado (stdout/stderr).
4.  **Observação:** O resultado é devolvido ao modelo como uma nova mensagem de contexto.
5.  **Resposta Final:** O modelo processa o resultado e responde ao usuário ou decide que precisa de mais uma etapa de execução.

### Integração com Obsidian
O agente interage com o Obsidian de duas formas redundantes e robustas:
- **API REST Local:** Via comandos `curl` documentados na Skill, o agente fala com o plugin *Obsidian Local REST API* para ações de interface (abrir notas, executar comandos do app).
- **Acesso Direto ao Disco:** Para buscas full-text, o agente utiliza ferramentas nativas do Linux como `grep` e `ls` dentro da pasta definida pela variável `OBSIDIAN_VAULT_PATH`. Isso contorna limitações ou bugs de plugins de terceiros e garante velocidade instantânea.

---

## 📋 Instalação e Configuração

### 1. Pré-requisitos
- **Modelo GGUF:** Um modelo de instrução (Recomendado: Qwen 2.5 7B ou Llama 3.1 8B).
- **Obsidian Plugin:** Instale e ative o plugin **Local REST API** no seu Obsidian.

### 2. Configuração do Ambiente
Crie um arquivo `.env` na raiz do projeto:

```ini
# Caminho para o modelo GGUF
MODEL_PATH=/caminho/para/seu/modelo.gguf

# Configurações do Obsidian
OBSIDIAN_API_TOKEN=seu_token_aqui
OBSIDIAN_VAULT_PATH=/home/usuario/Documents/Vault
```

### 3. Instalação
```bash
make install
```

---

## 🚀 Uso

Inicie o agente com o comando:
```bash
make agent
```

### O que você pode pedir:
- *"O que eu tenho anotado sobre o projeto X?"* (Ele vai buscar e ler a nota).
- *"Adicione uma etapa de 'revisão final' na minha lista de tarefas de hoje."* (Ele vai localizar sua Daily Note e usar `PATCH` para editar).
- *"Busque todas as notas que mencionam 'IA' e me dê um resumo."* (Ele vai usar `grep` recursivo e processar os arquivos).

---

## 🛡️ Segurança e Privacidade
- **100% Local:** Nada sai da sua máquina. O processamento da IA e o acesso aos arquivos são feitos localmente.
- **Transparência:** O agente imprime no terminal cada comando que está executando, permitindo que você audite as ações em tempo real.
