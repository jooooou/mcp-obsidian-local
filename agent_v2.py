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
        self.env_vars = {
            "OBSIDIAN_VAULT_PATH": os.getenv("OBSIDIAN_VAULT_PATH", "(Unknown)")
        }

    def log_trace(self, step_id: str, event_type: str, payload: Any):
        filename = f"{self.trace_dir}/{step_id}.jsonl"
        entry = {"ts": datetime.now().isoformat(), "event": event_type, "data": payload}
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # --- CORE TOOLS IMPLEMENTATION ---
    def execute_shell(self, command: str) -> str:
        print(f"    > Shell: {command}")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60, executable="/bin/bash"
            )
            output = result.stdout + (f"\n[STDERR] {result.stderr}" if result.stderr else "")
            if result.returncode != 0: output += f"\n[EXIT CODE] {result.returncode}"
            return output.strip() or "(No output)"
        except Exception as e: return f"Error: {str(e)}"

    def read_file(self, path: str) -> str:
        try:
            # Update Session Context
            self.session_context["last_accessed_file"] = path
            self.session_context["last_action"] = "read"
            
            with open(path, "r") as f: 
                content = f.read()
                return f"[METADATA] Source: {path}\n[CONTENT]\n{content}"
        except Exception as e: return f"Error: {str(e)}"        

    def write_file(self, path: str, content: str) -> str:
        try:
            # Update Session Context
            self.session_context["last_accessed_file"] = path
            self.session_context["last_action"] = "write"
            
            with open(path, "w") as f: f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e: return f"Error: {str(e)}"

    def list_agents(self) -> str:
        agents = []
        for f in glob.glob("agents/*.md"):
            try:
                data = frontmatter.load(f)
                agents.append({
                    "name": data.metadata.get("name", os.path.basename(f).replace(".md", "")),
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

    def list_skills(self) -> str:
        skills = glob.glob("skills/*/SKILL.md")
        return json.dumps([p.split("/")[1] for p in skills])

    def load_skill(self, name: str) -> str:
        path = f"skills/{name}/SKILL.md"
        if not os.path.exists(path):
            return f"Error: Skill '{name}' not found."
        try:
            with open(path, "r") as f:
                content = f.read()
                self.loaded_skills_content[name] = content
                return f"Skill '{name}' loaded."
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
            skills_text = "\n\n".join([f"--- SKILL: {n} ---\n{c}" for n, c in self.loaded_skills_content.items()])
            
            # INJECT SESSION CONTEXT INTO SYSTEM PROMPT
            session_info = ""
            if self.session_context["last_accessed_file"]:
                session_info = f"\nARQUIVO ATIVO: {self.session_context['last_accessed_file']}"

            system_prompt = f"""{config['system_prompt']}

---
AMBIENTE:
{json.dumps(self.env_vars, indent=2)}
{session_info}

SKILLS CARREGADAS:
{skills_text if skills_text else '(Nenhuma)'}

FERRAMENTAS DISPONÍVEIS:
{json.dumps(tools_schema, indent=2)}

REGRAS:
1. Responda de forma direta.
2. Use APENAS JSON para tools: <tool_call>{{"name": "...", "arguments": {{...}}}}</tool_call>
"""
            messages = [{"role": "system", "content": system_prompt}] + history[-15:]
            current_trace_id = f"{parent_trace_id}_{agent_name}_{step_counter}"
            self.log_trace(current_trace_id, "input", messages)

            print(f"⚡ {agent_name} thinking...")
            output = self.llm.create_chat_completion(
                messages=messages, temperature=0.1, max_tokens=1024, stop=["<|im_end|>"]
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
                    print(f"🛠️  {agent_name} calls {t_name}")
                    
                    result = "Tool unknown."
                    # Routing Logic (Simplified)
                    if t_name == "delegate_to_agent":
                        sub_res = self.run_agent(t_args.get("name"), t_args.get("task"), t_args.get("context"), current_trace_id)
                        result = sub_res
                    elif t_name == "execute_shell": result = self.execute_shell(t_args["command"])
                    elif t_name == "read_file": result = self.read_file(t_args["path"])
                    elif t_name == "write_file": result = self.write_file(t_args["path"], t_args["content"])
                    elif t_name == "list_agents": result = self.list_agents()
                    elif t_name == "get_agent_info": result = self.get_agent_info(t_args["name"])
                    elif t_name == "list_skills": result = self.list_skills()
                    elif t_name == "load_skill": result = self.load_skill(t_args["name"])
                    
                    print(f"   -> Result len: {len(result)}")
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

    def _get_tools_schema(self, allowed_tools: List[str]):
        # Full definitions (Simplified for brevity in display, but full logic remains)
        all_definitions = {
            "execute_shell": {"name": "execute_shell", "description": "Run bash command", "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
            "read_file": {"name": "read_file", "description": "Read file content", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
            "write_file": {"name": "write_file", "description": "Write/Overwrite file", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
            "list_agents": {"name": "list_agents", "description": "List available agents", "input_schema": {"type": "object", "properties": {}, "required": []}},
            "get_agent_info": {"name": "get_agent_info", "description": "Get details of an agent", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
            "delegate_to_agent": {"name": "delegate_to_agent", "description": "Delegate task", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "task": {"type": "string"}, "context": {"type": "string"}}, "required": ["name", "task"]}},
            "list_skills": {"name": "list_skills", "description": "List skill packages", "input_schema": {"type": "object", "properties": {}, "required": []}},
            "load_skill": {"name": "load_skill", "description": "Load skill", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        }
        schema = []
        for t in allowed_tools:
            if t in all_definitions: schema.append(all_definitions[t])
        return schema

if __name__ == "__main__":
    engine = AgentEngine(model_path=MODEL_PATH, n_ctx=N_CTX)
    engine.run_agent("brain", initial_task=None)