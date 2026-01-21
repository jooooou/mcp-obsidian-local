import json
import re
import requests
import datetime
from llama_cpp import Llama
import os
import sys
from dotenv import load_dotenv

# --- 1. CONFIGURAÇÃO ---
load_dotenv()

# Caminhos configuráveis via .env ou fallback
MODEL_PATH = os.getenv("MODEL_PATH")
MCP_URL = os.getenv("MCP_URL", "http://localhost:8080/tools/call")
N_CTX = 8192

# Verificação básica do modelo
if not os.path.exists(MODEL_PATH):
    print(f"❌ Erro: Modelo não encontrado em {MODEL_PATH}")
    print("Edite o arquivo .env ou ajuste a variável MODEL_PATH.")
    sys.exit(1)

print(f"⏳ Carregando modelo: {os.path.basename(MODEL_PATH)}...")

try:
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_gpu_layers=40, # Ajuste conforme sua VRAM
        main_gpu=0,
        n_threads=8,
        n_batch=1024,
        offload_kqv=True,
        mul_mat_q=True,
        verbose=False 
    )
except Exception as e:
    print(f"❌ Falha ao carregar modelo: {e}")
    sys.exit(1)

# --- 2. PROMPT DO SISTEMA ---
functions_description = """
- vault_list(): Lista arquivos no cofre. Retorna lista de caminhos.
- vault_read(path): Lê o conteúdo de um arquivo Markdown.
- vault_write(path, content): Cria ou substitui o conteúdo de um arquivo.
- vault_delete(path): Remove um arquivo.
- search(query): Busca arquivos pelo conteúdo.
- get_daily_note(date): Busca a nota do dia. Formato da data: YYYY-MM-DD.
"""

def get_system_prompt():
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    return f"""Você é um assistente inteligente integrado ao Obsidian (software de notas).
Data Atual: {current_date}

INSTRUÇÕES (ReAct Pattern):
1. Analise o pedido do usuário.
2. Pense passo a passo dentro de tags <thought>.
3. SE precisar de dados externos, gere uma <tool_call>.
4. Aguarde o resultado da ferramenta (que virá como mensagem de usuário).
5. Quando tiver a informação ou tiver concluído a ação, responda com <answer>.

FERRAMENTAS:
{functions_description}

EXEMPLO DE FLUXO:
User: Crie uma nota 'Teste' com 'Ola'.
Assistant: <thought>Devo criar um arquivo.</thought>
<tool_call>{{"name": "vault_write", "arguments": {{"path": "Teste.md", "content": "Ola"}}}}</tool_call>
User: RESULTADO DA FERRAMENTA: "Success"
Assistant: <thought>Ação concluída. Vou avisar o usuário.</thought>
<answer>Nota criada com sucesso!</answer>
"""

# --- 3. FUNÇÕES AUXILIARES ---
history = []

def trim_history(max_messages=10):
    """Mantém apenas as últimas N mensagens para não estourar o contexto."""
    global history
    if len(history) > max_messages:
        # Mantém sempre a coerência removendo pares antigos, mas cuidado para não quebrar fluxos
        history = history[-max_messages:]

def add_to_history(role, content):
    history.append({"role": role, "content": content})

def execute_tool_call(tool_call):
    print(f"⚙️  Tool: {tool_call.get('name')} {tool_call.get('arguments')}")
    try:
        response = requests.post(MCP_URL, json=tool_call, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}
    except requests.RequestException as e:
        return {"error": f"Connection Error: {str(e)}"}

def parse_llm_response(text):
    # Regex mais flexível para capturar o conteúdo mesmo se o LLM errar espaçamento
    thought = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
    tool_call = re.search(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
    answer = re.search(r"<answer>(.*?)</answer>", text, re.DOTALL)

    parsed_thought = thought.group(1).strip() if thought else None
    
    if tool_call:
        try:
            # Tenta limpar o JSON (alguns LLMs colocam markdown ```json dentro da tag)
            raw_json = tool_call.group(1).strip()
            raw_json = re.sub(r"^```json", "", raw_json).replace("```", "").strip()
            action = json.loads(raw_json)
            return parsed_thought, action, "tool_call"
        except json.JSONDecodeError:
            return parsed_thought, {"error": "LLM gerou JSON inválido"}, "error"
            
    if answer:
        return parsed_thought, answer.group(1).strip(), "answer"
    
    # Fallback: Se não tem tag de answer nem tool, assume que é resposta direta
    if not tool_call and not answer:
        return parsed_thought, text.replace(thought.group(0) if thought else "", "").strip(), "answer"
        
    return parsed_thought, None, "continue"

# --- 4. LOOP PRINCIPAL ---
if __name__ == "__main__":
    print("\n🤖 Obsidian Agent Iniciado. Digite 'sair' para encerrar.")
    
    while True:
        try:
            user_input = input("\n👤 Você: ")
            if user_input.lower() in ["sair", "exit", "quit"]: break
            
            add_to_history("user", user_input)
            trim_history(15) 
            
            step = 0
            MAX_STEPS = 5
            
            while step < MAX_STEPS:
                system_prompt = get_system_prompt()
                messages = [{"role": "system", "content": system_prompt}] + history
                
                print("🤖 (Pensando...)")
                output = llm.create_chat_completion(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=1024,
                    stop=["<|im_end|>", "<|endoftext|>"] # Stops comuns
                )
                
                full_response = output["choices"][0]["message"]["content"]
                thought, content, type_ = parse_llm_response(full_response)
                
                # Importante: Adiciona o que o LLM gerou ao histórico para ele "lembrar" do próprio raciocínio
                add_to_history("assistant", full_response)

                if thought:
                    print(f"💭 {thought}")

                if type_ == "tool_call":
                    # Executa a ferramenta
                    result = execute_tool_call(content)
                    
                    # TRUQUE: Devolvemos o resultado como uma mensagem de USUÁRIO.
                    # Isso simula o ambiente devolvendo a informação.
                    result_msg = f"RESULTADO DA FERRAMENTA ({content.get('name')}): {json.dumps(result, ensure_ascii=False)}"
                    add_to_history("user", result_msg)
                    
                    step += 1
                    continue # Volta para o início do loop para o LLM processar o resultado

                elif type_ == "answer":
                    print(f"🤖 {content}")
                    break # Fim da resposta ao usuário
                
                elif type_ == "error":
                    print("⚠️ Erro de parsing no LLM. Tentando recuperar...")
                    add_to_history("user", "Erro: Você gerou um JSON inválido. Tente novamente.")
                    step += 1
                    continue
                
                else:
                    # Se caiu aqui, é uma resposta sem tags (fallback)
                    print(f"🤖 {content}")
                    break

            if step >= MAX_STEPS:
                print("⚠️ Limite de passos atingido (Loop infinito evitado).")

        except KeyboardInterrupt:
            print("\nParando...")
            break