import json
import re
import subprocess
import os
import sys
import glob
import time
import frontmatter
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from llama_cpp import Llama

# --- CONFIGURATION ---
load_dotenv()
MODEL_PATH = os.getenv("MODEL_PATH")
N_CTX = 8192

if not MODEL_PATH or not os.path.exists(MODEL_PATH):
    print(f"❌ Error: Model not found at {MODEL_PATH}")
    print("Please set MODEL_PATH in your .env file.")
    sys.exit(1)

# --- UTILS ---
def load_agent_config(agent_name: str) -> Dict[str, Any]:
    path = f"agents/{agent_name.lower()}.md"
    if not os.path.exists(path):
        raise ValueError(f"Agent '{agent_name}' not found at {path}")
    post = frontmatter.load(path)
    return {
        "name": post.metadata.get("name", agent_name),
        "description": post.metadata.get("description", ""),
        "model": post.metadata.get("model", "default"),
        "allowed_tools": post.metadata.get("tools", []),
        "system_prompt": post.content
    }

# --- ENGINE ---
class AgentEngine:
    def __init__(self, model_path: str, n_ctx: int = 8192):
        print(f"⏳ Loading model: {os.path.basename(model_path)}...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=40,
            main_gpu=0,
            n_threads=8,
            verbose=False
        )
        self.n_ctx = n_ctx
        self.trace_dir = f"traces/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        os.makedirs(self.trace_dir, exist_ok=True)
        print(f"🕵️  Tracing enabled. Logs: {self.trace_dir}")
        self.loaded_skills_content = {}
        
        # Session Context (Shared Memory)
        self.session_context = {
            "last_accessed_file": None,
            "last_action": None
        }

    def log_trace(self, step_id: str, event_type: str, payload: Any):
        filename = f"{self.trace_dir}/{step_id}.jsonl"
        entry = {"ts": datetime.now().isoformat(), "event": event_type, "data": payload}
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # --- UTILS ---
    def _resolve_path(self, path: str) -> str:
        """Resolve environment variables and ~ in paths."""
        return os.path.expanduser(os.path.expandvars(path))

    # --- CORE TOOLS IMPLEMENTATION ---
    def execute_shell(self, command: str) -> str:
        print(f"    > Shell: {command}")
        try:
            # Pass current environment (with loaded .env vars) to subprocess
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=60, 
                executable="/bin/bash",
                env=os.environ.copy()
            )
            output = result.stdout + (f"\n[STDERR] {result.stderr}" if result.stderr else "")
            if result.returncode != 0: output += f"\n[EXIT CODE] {result.returncode}"
            return output.strip() or "(No output)"
        except Exception as e: return f"Error: {str(e)}"

    def read_file(self, path: str) -> str:
        path = self._resolve_path(path)
        try:
            # Update Session Context
            self.session_context["last_accessed_file"] = path
            self.session_context["last_action"] = "read"
            
            with open(path, "r") as f: 
                content = f.read()
                return f"[METADATA] Source: {path}\n[CONTENT]\n{content}"
        except Exception as e: return f"Error: {str(e)}"        

    def write_file(self, path: str, content: str) -> str:
        path = self._resolve_path(path)
        try:
            # Update Session Context
            self.session_context["last_accessed_file"] = path
            self.session_context["last_action"] = "write"
            
            with open(path, "w") as f: f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e: return f"Error: {str(e)}"

    def edit_file(self, path: str, operation: str, text: str, target_text: str = None) -> str:
        path = self._resolve_path(path)
        try:
            if not os.path.exists(path): return f"Error: File {path} not found."
            
            with open(path, "r") as f: content = f.read()
            
            if operation == "append":
                new_content = content + "\n" + text
            elif operation == "replace":
                if not target_text: return "Error: 'target_text' is required for replace operation."
                if target_text not in content: return "Error: 'target_text' not found in file."
                new_content = content.replace(target_text, text)
            else:
                return "Error: Invalid operation. Use 'append' or 'replace'."
            
            with open(path, "w") as f: f.write(new_content)
            
            self.session_context["last_accessed_file"] = path
            self.session_context["last_action"] = "edit"
            return f"Successfully edited {path} (mode: {operation})"
        except Exception as e: return f"Error: {str(e)}"

    def list_agents(self) -> str:
        agents = []
        for f in glob.glob("agents/*.md"):
            try:
                data = frontmatter.load(f)
                name = data.metadata.get("name", os.path.basename(f).replace(".md", ""))
                # Filter out 'brain' to prevent self-delegation
                if name.lower() != "brain":
                    agents.append({
                        "name": name,
                        "description": data.metadata.get("description", "No description")
                    })
            except: continue
        return json.dumps(agents, indent=2)

    def get_agent_info(self, agent_name: str) -> str:
        try:
            cfg = load_agent_config(agent_name)
            return json.dumps({
                "name": cfg["name"],
                "description": cfg["description"],
                "tools": cfg["allowed_tools"]
            }, indent=2)
        except Exception as e: return f"Error: {str(e)}"

    def search_skills(self, query: str) -> str:
        results = []
        # Tokenize query: split by spaces, lowercase, ignore short words (<3 chars)
        query_tokens = [t for t in query.lower().split() if len(t) > 2]
        
        if not query_tokens:
            return "Query muito curta ou vazia."

        # Search recursively in all .md files within skills/
        for filepath in glob.glob("skills/**/*.md", recursive=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    # Read first 1000 chars for header matching
                    header = f.read(1000)
                
                # Check match: if ANY token is in filepath OR header
                target_text = (filepath + " " + header).lower()
                if any(token in target_text for token in query_tokens):
                    # Extract description from frontmatter if available
                    desc = "No description"
                    match = re.search(r"description:\s*(.+)", header, re.IGNORECASE)
                    if match:
                        desc = match.group(1).strip()
                    
                    results.append(f"- Path: {filepath}\n  Description: {desc}")
            except Exception: continue
            
        if not results:
            return "Nenhuma skill encontrada para esses termos."
        return "\n".join(results)

    def list_skills_page(self, page: int = 1) -> str:
        # Group by directory
        skill_dirs = sorted(glob.glob("skills/*/"))
        total_skills = len(skill_dirs)
        
        if total_skills == 0: return "Nenhuma skill encontrada."
        
        PAGE_SIZE = 5
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        current_batch = skill_dirs[start_idx:end_idx]
        
        if not current_batch: return f"Página {page} vazia. Total de skills: {total_skills}."
        
        results = []
        for d in current_batch:
            skill_name = os.path.basename(os.path.normpath(d)).upper()
            
            # Get main description
            desc = "Conjunto de ferramentas."
            for index_file in ["_index.md", "SKILL.md"]:
                if os.path.exists(os.path.join(d, index_file)):
                    try:
                        data = frontmatter.load(os.path.join(d, index_file))
                        desc = data.metadata.get("description", desc)
                        break
                    except: continue
            
            # List sub-files with full relative paths
            sub_files = [f for f in glob.glob(f"{d}/*.md") if not f.endswith("_index.md") and not f.endswith("SKILL.md")]
            sub_list = "\n   - ".join(sub_files) if sub_files else "   (Nenhum arquivo extra)"
            
            results.append(f"📦 {skill_name}: {desc}\n   - {sub_list}")
            
        footer = f"\n[Página {page} de {((total_skills - 1) // PAGE_SIZE) + 1}. Total: {total_skills} skills]"
        return "\n".join(results) + footer

    def load_skill(self, path: str) -> str:
        if not os.path.exists(path) or not path.startswith("skills/"):
            return "Error: Invalid skill path or file not found."
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                # Use path as key to allow multiple files from same skill package
                self.loaded_skills_content[path] = content
                return f"Skill instructions from '{path}' loaded."
        except Exception as e: return f"Error: {str(e)}"

    # --- AGENT RUNTIME ---
    def run_agent(self, agent_name: str, initial_task: str, context: str = None, parent_trace_id: str = "root") -> str:
        try:
            config = load_agent_config(agent_name)
        except Exception as e: return f"Failed to load agent {agent_name}: {e}"

        print(f"\n🤖 Activating Agent: {agent_name.upper()}")
        history = []
        
        if initial_task:
            content = initial_task
            if context: content += f"\n\n--- CONTEXTO ---\n{context}"
            history.append({"role": "user", "content": content})

        step_counter = 0
        
        while True:
            if initial_task and step_counter == 0: pass
            elif len(history) == 0 or history[-1]["role"] == "assistant":
                try:
                    user_input = input(f"👤 {agent_name} > ")
                    if user_input.lower() in ["exit", "quit"]: return "User terminated."
                    history.append({"role": "user", "content": user_input})
                except EOFError: return "Session ended."

            allowed_tools = config["allowed_tools"]
            tools_schema = self._get_tools_schema(allowed_tools)
            formatted_tools = self._format_tools_display(tools_schema)
            
            # Format loaded skills showing origin file
            skills_text = ""
            if self.loaded_skills_content:
                skills_text = "\n\n".join([f"--- SKILL FILE: {p} ---\n{c}" for p, c in self.loaded_skills_content.items()])
            else:
                skills_text = "(Nenhuma skill carregada. Use search_skills se precisar.)"
            
            # INJECT SESSION CONTEXT INTO SYSTEM PROMPT
            session_info = ""
            if self.session_context["last_accessed_file"]:
                session_info = f"\nARQUIVO ATIVO: {self.session_context['last_accessed_file']}"

            system_prompt = f"""{config['system_prompt']}

---
CONCEITOS DO SISTEMA:
1. NATUREZA DA "SKILL":
   - Uma Skill é uma extensão de conhecimento que ensina a operar sistemas ou realizar funções técnicas.
   - Ela fornece a **Sintaxe Correta** e as **Variáveis de Ambiente** (ex: $VAR) necessárias para a operação.
   - **POLÍTICA ZERO-KNOWLEDGE:** Você não sabe operar o sistema. É proibido executar comandos baseados em conhecimento prévio. Você DEVE ler o manual (`load_skill`) antes de usar qualquer ferramenta de execução.

2. USO ESTRATÉGICO DE `search_skills`:
   - O objetivo é encontrar **Capacidades**, **Ferramentas** ou **Operações Funcionais**.
   - **PROIBIÇÃO DE ASSUNTO:** Jamais inclua o assunto da solicitação na busca de skills. Busque apenas pela funcionalidade técnica necessária (ex: buscar, ler, sistema).
   - O fluxo lógico obrigatório é: Descobrir o Método (Skill) -> **CARREGAR o Método (`load_skill`)** -> Executar a SINTAXE documentada usando as VARIÁVEIS (ex: $VAR) de forma estritamente literal.
   - **RESOLUÇÃO DE VARIÁVEIS:** O sistema já possui as variáveis ($VAR) configuradas. Use-as literalmente; o shell as resolverá. Nunca as substitua por caminhos manuais.

CONTEXTO DE SESSÃO:
{session_info if session_info else "(Nenhum arquivo acessado recentemente)"}

SKILLS ATIVAS (Capacidades Carregadas):
{skills_text}

FERRAMENTAS DISPONÍVEIS:
{formatted_tools}

REGRAS:
1. Responda de forma direta.
2. Use APENAS JSON para tools: <tool_call>{{"name": "...", "arguments": {{...}}}}</tool_call>
3. **PESQUISA DE SKILLS:** Busque sempre pelo **COMO** (ação técnica), nunca pelo **O QUE** (assunto do usuário).
4. **VISIBILIDADE:** O usuário NÃO VÊ as respostas dos agentes. Se um agente encontrar a informação, você DEVE transcrevê-la INTEGRALMENTE na sua resposta final. Jamais oculte dados sob frases como 'está pronto'.
5. **VARIÁVEIS DISPONÍVEIS:** Todas as variáveis de ambiente (ex: $VAR) citadas nas skills estão carregadas no shell. Use-as literalmente; não tente substituí-las por caminhos manuais.
6. Se encontrar barreiras, tente de outra forma (pelo menos 2 tentativas).
"""
            messages = [{"role": "system", "content": system_prompt}] + history[-15:]
            current_trace_id = f"{parent_trace_id}_{agent_name}_{step_counter}"
            self.log_trace(current_trace_id, "input", messages)

            print(f"⚡ {agent_name} thinking...")
            output = self.llm.create_chat_completion(
                messages=messages, temperature=0.1, max_tokens=4096, stop=["<|im_end|>"]
            )
            response_text = output["choices"][0]["message"]["content"]
            history.append({"role": "assistant", "content": response_text})
            self.log_trace(current_trace_id, "output", response_text)

            tool_match = re.search(r"<tool_call>(.*?)</tool_call>", response_text, re.DOTALL)
            
            if tool_match:
                tool_json = tool_match.group(1).strip()
                if tool_json.startswith("```"): tool_json = tool_json.split("\n", 1)[1].rsplit("\n", 1)[0]
                
                try:
                    tool_call = json.loads(tool_json)
                    t_name = tool_call["name"]
                    t_args = tool_call.get("arguments", {})
                    print(f"🛠️  {agent_name} calls {t_name} with {json.dumps(t_args)}")
                    
                    result = "Tool unknown."
                    # Routing Logic (Simplified)
                    if t_name == "delegate_to_agent":
                        sub_res = self.run_agent(t_args.get("name"), t_args.get("task"), t_args.get("context"), current_trace_id)
                        result = sub_res
                    elif t_name == "execute_shell": result = self.execute_shell(t_args["command"])
                    elif t_name == "read_file": result = self.read_file(t_args["path"])
                    elif t_name == "write_file": result = self.write_file(t_args["path"], t_args["content"])
                    elif t_name == "edit_file": result = self.edit_file(t_args["path"], t_args["operation"], t_args["text"], t_args.get("target_text"))
                    elif t_name == "list_agents": result = self.list_agents()
                    elif t_name == "get_agent_info": result = self.get_agent_info(t_args["name"])
                    elif t_name == "search_skills": result = self.search_skills(t_args["query"])
                    elif t_name == "list_skills_page": result = self.list_skills_page(t_args.get("page", 1))
                    elif t_name == "load_skill": result = self.load_skill(t_args["path"])
                    
                    # CLI Display Logic
                    display_result = result
                    if t_name == "delegate_to_agent" and len(result) > 200:
                         display_result = result[:200] + "... (truncated)"
                    
                    print(f"   -> Result: {display_result}")
                    # Prefix Agent Name for Clarity
                    result_prefix = f"[AGENTE: {agent_name.upper()}] " if agent_name != "brain" else ""
                    history.append({"role": "user", "content": f"TOOL RESULT ({t_name}): {result_prefix}{result}"})
                    self.log_trace(current_trace_id, "tool_result", result)
                    
                except Exception as e:
                    history.append({"role": "user", "content": f"Tool Error: {str(e)}"})
            
            else:
                if initial_task: 
                    clean_res = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
                    return clean_res
                print(f"🤖 {agent_name}: {response_text}")

            step_counter += 1
            if step_counter > 15: return "Error: Max steps reached."

    def _format_tools_display(self, tools_schema: List[Dict]) -> str:
        lines = []
        for tool in tools_schema:
            lines.append(f"> {tool['name']}")
            lines.append(f"  Descrição: {tool['description']}")
            args = ", ".join([f"{k} ({v['type']})" for k, v in tool['input_schema']['properties'].items()])
            lines.append(f"  Argumentos: {args}")
            lines.append("")
        return "\n".join(lines).strip()

    def _get_tools_schema(self, allowed_tools: List[str]):
        # Full definitions (Simplified for brevity in display, but full logic remains)
        all_definitions = {
            "execute_shell": {"name": "execute_shell", "description": "Executa comandos Shell/Bash. Permite listar (ls), buscar (grep/find), ler (cat), git e outras ferramentas nativas do Linux.", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            "read_file": {"name": "read_file", "description": "Lê o conteúdo de um arquivo local.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            "write_file": {"name": "write_file", "description": "Escreve ou sobrescreve um arquivo INTEIRO.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            "edit_file": {"name": "edit_file", "description": "Edita um arquivo parcialmente. Use operation='append' para adicionar ao final, ou 'replace' para substituir texto.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "operation": {"type": "string", "enum": ["append", "replace"]}, "text": {"type": "string"}, "target_text": {"type": "string"}}, "required": ["path", "operation", "text"]}},
            "list_agents": {"name": "list_agents", "description": "Lista os agentes disponíveis.", "input_schema": {"type": "object", "properties": {}, "required": []}},
            "get_agent_info": {"name": "get_agent_info", "description": "Obtém detalhes de um agente.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
            "delegate_to_agent": {"name": "delegate_to_agent", "description": "Delega uma tarefa para outro agente.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "task": {"type": "string"}, "context": {"type": "string"}}, "required": ["name", "task"]}},
            "search_skills": {"name": "search_skills", "description": "Localiza MANUAIS DE INSTRUÇÃO e EXTENSÕES DE CONHECIMENTO. A query deve focar no MÉTODO TÉCNICO ou SISTEMA desejado. Não indexa o conteúdo ou assunto do usuário.", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
            "list_skills_page": {"name": "list_skills_page", "description": "Lista todas as skills disponíveis paginadas. Use quando a busca falhar.", "input_schema": {"type": "object", "properties": {"page": {"type": "integer", "default": 1}}, "required": []}},
            "load_skill": {"name": "load_skill", "description": "Carrega as instruções de um arquivo de skill específico.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
        }
        schema = []
        for t in allowed_tools:
            if t in all_definitions: schema.append(all_definitions[t])
        return schema

if __name__ == "__main__":
    engine = AgentEngine(model_path=MODEL_PATH, n_ctx=N_CTX)
    engine.run_agent("brain", initial_task=None)