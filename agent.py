import json
import re
import subprocess
import os
import sys
import glob
from typing import List, Dict, Any
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

# --- CORE AGENT ---
class SkillAgent:
    def __init__(self, model_path: str, n_ctx: int = 8192):
        print(f"⏳ Loading model: {os.path.basename(model_path)}...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=40, # Adjust based on your GPU
            main_gpu=0,
            n_threads=8,
            verbose=False
        )
        self.history = []
        self.loaded_skills = {} # name -> content
        self.n_ctx = n_ctx
    
    # OBSIDIAN_VAULT_PATH needs to be accessible inside run()
    OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "(Unknown - ask user if needed)")

    def count_tokens(self, text: str) -> int:
        return len(self.llm.tokenize(text.encode("utf-8")))

    def get_context_usage(self):
        # Rough estimation of history + system prompt
        total_tokens = sum(self.count_tokens(msg["content"]) for msg in self.history)
        return total_tokens, self.n_ctx

    # --- TOOLS (Programmatic) ---
    def execute_shell(self, command: str) -> str:
        """Executes a shell command and returns output."""
        print(f"    > Executing: {command}")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=60, # Increased timeout
                executable="/bin/bash"
            )
            output = result.stdout
            if result.stderr:
                # Include stderr for debugging but don't fail just because of it (curl -v writes to stderr)
                output += f"\n[STDERR]\n{result.stderr}"
            
            # Check return code
            if result.returncode != 0:
                output += f"\n[EXIT CODE] {result.returncode}"
                
            return output.strip() or "(No output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after 60s. Command was: {command}"
        except Exception as e:
            return f"Error: {str(e)}"

    def read_file(self, path: str) -> str:
        """Reads a file from disk."""
        try:
            with open(path, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def list_skills(self) -> List[str]:
        """Lists available skills in the skills/ directory."""
        skills = glob.glob("skills/*/SKILL.md")
        return [p.split("/")[1] for p in skills]

    def load_skill(self, name: str) -> str:
        """Loads a skill's instructions into the context."""
        path = f"skills/{name}/SKILL.md"
        if not os.path.exists(path):
            return f"Error: Skill '{name}' not found."
        
        content = self.read_file(path)
        self.loaded_skills[name] = content
        return f"Skill '{name}' loaded successfully. Instructions added to context."

    def get_tools_schema(self):
        """Returns the JSON schema for the core tools."""
        return [
            {
                "name": "execute_shell",
                "description": "Execute a CLI command in the system terminal.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The bash command to run."}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "read_file",
                "description": "Read the content of a file.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to the file."}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "list_skills",
                "description": "List available skills that can be loaded.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "load_skill",
                "description": "Load a specific skill (documentation) into context.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The name of the skill (e.g., 'obsidian')."}
                    },
                    "required": ["name"]
                }
            }
        ]

    # --- MAIN LOOP ---
    def run(self):
        print("\n🚀 Skill-Based Agent Started. Type 'exit' to quit.")
        
        while True:
            try:
                # 1. Context Visualization
                used, total = self.get_context_usage()
                print(f"\n🧠 Context: {used}/{total} tokens ({used/total:.1%})")
                
                # 2. User Input
                user_input = input("👤 You: ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                self.history.append({"role": "user", "content": user_input})
                
                # 3. Generation Loop (Thought -> Tool -> Answer)
                step = 0
                max_steps = 10
                
                while step < max_steps:
                    # Construct System Prompt
                    skills_text = "\n\n".join([f"--- SKILL: {name} ---\n{content}" for name, content in self.loaded_skills.items()])
                    
                    system_prompt = f"""
                    Você é um Assistente Avançado de IA com acesso a ferramentas locais.\n\nVARIÁVEIS DE AMBIENTE:\n- OBSIDIAN_VAULT_PATH: {self.OBSIDIAN_VAULT_PATH}\n\nFERRAMENTAS PRINCIPAIS:\n{json.dumps(self.get_tools_schema(), indent=2)}\n\nSKILLS CARREGADAS:\n{skills_text if skills_text else '(Nenhuma skill carregada. Use \'list_skills\' para descobrir capacidades.)'}\n\nINSTRUÇÕES:\n1. **CONSCIÊNCIA SITUACIONAL:** Para conversas gerais, responda naturalmente.\n2. **AÇÃO IMEDIATA:** Se o usuário pedir informações, busque-as e ENTREGUE o conteúdo final. Se encontrar um arquivo relevante, LEIA-O imediatamente com `read_file`. Não peça permissão para abrir arquivos que você localizou; seu objetivo é trazer a resposta pronta.\n3. **FLUXO DE DESCOBERTA:** Antes de dizer \"não sei\" ou pedir caminhos, use 'list_skills' para checar se há ferramentas relevantes (como 'obsidian' para notas). Se houver, use 'load_skill' e siga o manual.\n4. **FIDELIDADE DE BUSCA:** Ao buscar por algo, use os termos no idioma original do usuário. Considere que os arquivos podem estar em português ou inglês. Se a primeira busca falhar, tente sinônimos.\n5. **RACIOCÍNIO:** Use <thought>...</thought> para planejar. Explique por que você decidiu carregar uma skill ou fazer uma busca.\n6. **CHAMADA DE FERRAMENTA (IMPORTANTE):** 
                    - Retorne APENAS o JSON cru dentro da tag.
                    - NÃO use blocos de código markdown (```json).
                    - Formato Obrigatório: <tool_call>{{"name": "nome_da_tool", "arguments": {{"arg1": "valor"}}}}</tool_call>
                    """
                    
                    messages = [{"role": "system", "content": system_prompt}] + self.history[-15:] # Keep last 15 messages
                    
                    print("🤖 (Thinking...)")
                    output = self.llm.create_chat_completion(
                        messages=messages,
                        temperature=0.1,
                        max_tokens=1024,
                        stop=["<|im_end|>"]
                    )
                    
                    response_text = output["choices"][0]["message"]["content"]
                    self.history.append({"role": "assistant", "content": response_text})
                    
                    # Parse Response
                    thought_match = re.search(r"<thought>(.*?)</thought>", response_text, re.DOTALL)
                    tool_match = re.search(r"<tool_call>(.*?)</tool_call>", response_text, re.DOTALL)
                    
                    if thought_match:
                        print(f"💭 {thought_match.group(1).strip()}")
                    
                    if tool_match:
                        tool_json = tool_match.group(1).strip()
                        # Cleanup markdown code blocks if present
                        if tool_json.startswith("```"):
                            tool_json = tool_json.split("\n", 1)[1].rsplit("\n", 1)[0]
                        
                        try:
                            tool_call = json.loads(tool_json)
                            name = tool_call["name"]; args = tool_call.get("arguments", {})
                            
                            # Log visual da chamada
                            print(f"\n🛠️  Chamando ferramenta: {name}")
                            if args: print(f"📦 Argumentos: {json.dumps(args, indent=2, ensure_ascii=False)}")
                            
                            result = "Unknown tool"
                            if name == "execute_shell":
                                result = self.execute_shell(args["command"])
                            elif name == "read_file":
                                result = self.read_file(args["path"])
                            elif name == "list_skills":
                                result = str(self.list_skills())
                            elif name == "load_skill":
                                result = self.load_skill(args["name"])
                            
                            print(f"⚙️  Result: {result[:200]}..." if len(result) > 200 else f"⚙️  Result: {result}")
                            
                            # Feed result back
                            self.history.append({"role": "user", "content": f"TOOL RESULT ({name}): {result}"})
                            step += 1
                            continue
                            
                        except json.JSONDecodeError:
                            print("❌ Error: Invalid JSON in tool call")
                            self.history.append({"role": "user", "content": "Error: Invalid JSON in tool call."})
                            continue
                    
                    # If no tool call, assume it's the answer
                    if not tool_match:
                        print(f"🤖 {response_text.replace(thought_match.group(0) if thought_match else '', '').strip()}")
                        break
                
            except KeyboardInterrupt:
                print("\nStopped.")
                break

if __name__ == "__main__":
    if not os.getenv("OBSIDIAN_API_TOKEN"):
        print("⚠️  Warning: OBSIDIAN_API_TOKEN not set. Obsidian skill might fail.")

    agent = SkillAgent(model_path=MODEL_PATH, n_ctx=N_CTX)
    agent.run()