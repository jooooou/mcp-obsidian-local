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

# --- 2. CONFIGURAÇÃO DE FERRAMENTAS DINÂMICAS ---

class ToolRegistry:
    def __init__(self, mcp_url):
        self.mcp_url = mcp_url
        self.available_tools = [] # Cache de todas as ferramentas disponíveis no servidor
        self.active_tools = {}    # Ferramentas atualmente carregadas no contexto do LLM
        self.load_definitions()

    def load_definitions(self):
        """Busca todas as definições do servidor ao iniciar."""
        try:
            response = requests.get(f"{self.mcp_url.replace('/tools/call', '/tools')}", timeout=10)
            if response.status_code == 200:
                self.available_tools = response.json()
            else:
                self.available_tools = [] 
        except Exception as e:
            self.available_tools = []
            
        # Inicia APENAS com a ferramenta de busca de ferramentas
        self.active_tools = {}
        self.active_tools["search_tools"] = {
            "name": "search_tools",
            "description": "Busca ferramentas disponíveis no sistema baseada em uma query de busca.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo de busca para encontrar a ferramenta ideal."}
                },
                "required": ["query"]
            }
        }

    def search(self, query):
        """Busca por palavras-chave nas ferramentas disponíveis e as ativa."""
        query_words = query.lower().split()
        found = []
        
        for tool in self.available_tools:
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            
            if any(word in name or word in desc for word in query_words):
                if tool["name"] not in self.active_tools:
                    found.append(tool)
                    self.active_tools[tool["name"]] = tool
        
        return found

    

    def get_prompt_definitions(self):
        """Gera a string JSON para o System Prompt com as ferramentas ativas."""
        return json.dumps(list(self.active_tools.values()), indent=2, ensure_ascii=False)

# Inicializa o registro
base_url = MCP_URL if "tools/call" in MCP_URL else f"{MCP_URL}/tools/call"
registry = ToolRegistry(base_url)


def get_system_prompt():
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    tools_json = registry.get_prompt_definitions()
    
    return f"""Você é um assistente integrado ao Obsidian.
Data Atual: {current_date}

FERRAMENTAS DISPONÍVEIS:
{tools_json}

INSTRUÇÕES:
1. Analise a solicitação do usuário.
2. Se as ferramentas listadas acima não forem suficientes, use 'search_tools' para descobrir novas capacidades.
3. Se identificar a ferramenta correta (pela busca ou lista de sugestões), carregue-a e USE-A imediatamente para atender ao pedido. Não peça permissão para fazer o que foi solicitado.
4. Utilize as tags <thought> para raciocinar antes de cada ação.
5. Formato de chamada: <tool_call>{{"name": "...", "arguments": {{...}}}}</tool_call>
"""

# --- 3. FUNÇÕES AUXILIARES ---
history = []

def trim_history(max_messages=10):
    global history
    if len(history) > max_messages:
        history = history[-max_messages:]

def add_to_history(role, content):
    history.append({"role": role, "content": content})

def execute_tool_call(tool_call):

    name = tool_call.get("name")

    args = tool_call.get("arguments", {})

    

    print(f"⚙️  Tool: {name} {args}")

    

    # Intercepta a chamada local de 'search_tools'

    if name == "search_tools":

        query = args.get("keywords") or args.get("query")

        results = registry.search(query)

        

        if not results:

            # Fallback: Se não achou nada específico, lista os NOMES de tudo que existe

            all_names = [t["name"] for t in registry.available_tools]

            return f"Nenhuma ferramenta encontrada especificamente para '{query}'. Mas existem estas ferramentas no sistema: {all_names}. Tente buscar pelo nome de uma delas."

            

        return f"Novas ferramentas carregadas: {[t['name'] for t in results]}. Agora você pode usá-las."



    # Chamadas remotas via MCP

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