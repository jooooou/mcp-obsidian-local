from fastapi import FastAPI, HTTPException
import requests
import json
import re
import logging
from dotenv import load_dotenv
import os
import difflib

load_dotenv()

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

OBSIDIAN_API_URL = os.getenv("OBSIDIAN_API_URL")
API_TOKEN = os.getenv("OBSIDIAN_API_TOKEN")

if not API_TOKEN:
    logger.critical("ERRO CRÍTICO: Token da API não encontrado. Verifique o arquivo .env")
    raise RuntimeError("OBSIDIAN_API_TOKEN não configurado no arquivo .env")

# --- DEFINIÇÃO DE FERRAMENTAS (JSON SCHEMA) ---
TOOL_DEFINITIONS = [
    {
        "name": "vault_list",
        "description": "Lista todos os arquivos presentes no cofre (vault) do Obsidian.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "vault_read",
        "description": "Lê o conteúdo de um arquivo Markdown específico.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "O caminho relativo do arquivo (ex: 'Pasta/Nota.md')"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "vault_write",
        "description": "Substitui completamente o conteúdo de um arquivo existente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Caminho do arquivo"},
                "content": {"type": "string", "description": "Novo conteúdo do arquivo"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "vault_create",
        "description": "Cria um novo arquivo. Falha se o arquivo já existir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Caminho do novo arquivo"},
                "content": {"type": "string", "description": "Conteúdo inicial (opcional)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "vault_delete",
        "description": "Remove permanentemente um arquivo do cofre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Caminho do arquivo a ser deletado"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "search",
        "description": "Busca arquivos pelo nome (fuzzy) ou conteúdo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_daily_note",
        "description": "Busca a nota diária correspondente a uma data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Data no formato YYYY-MM-DD"}
            },
            "required": ["date"]
        }
    },
    {
        "name": "execute_command",
        "description": "Executa um comando interno do Obsidian pelo ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command_id": {"type": "string", "description": "ID do comando (ex: 'editor:toggle-bold')"}
            },
            "required": ["command_id"]
        }
    }
]

def call_obsidian_api(endpoint: str, method: str = "GET", data: dict = None, is_text: bool = False):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
    }
    
    url = f"{OBSIDIAN_API_URL}{endpoint}"
    
    try:
        if is_text:
            headers["Content-Type"] = "text/markdown"
            request_data = data.get("content", "") if data else ""
        else:
            headers["Content-Type"] = "application/json"
            request_data = json.dumps(data) if data else None

        logger.info(f"Chamando API Obsidian: {method} {url}")
        
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, data=request_data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, data=request_data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
            
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text
        
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_detail += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        logger.error(f"Erro na API Obsidian: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Obsidian API error: {error_detail}")

@app.get("/tools")
async def list_tools():
    """Retorna a lista de ferramentas disponíveis e seus schemas."""
    return TOOL_DEFINITIONS

@app.post("/tools/call")
async def call_tool(request: dict):
    name = request.get("name")
    arguments = request.get("arguments", {})
    logger.info(f"Chamada de ferramenta: {name} com argumentos: {arguments}")
    
    try:
        if name == "vault_list":
            return call_obsidian_api("/vault/")
            
        elif name == "vault_read":
            path = arguments.get("path") or arguments.get("filename")
            if not path: raise KeyError("path")
            return call_obsidian_api(f"/vault/{path}")
            
        elif name == "vault_write":
            path = arguments.get("path") or arguments.get("filename")
            if not path: raise KeyError("path")
            content = arguments.get("content")
            return call_obsidian_api(f"/vault/{path}", "PUT", {"content": content}, is_text=True)
            
        elif name == "vault_create":
            path = arguments.get("path") or arguments.get("filename")
            if not path: raise KeyError("path")
            content = arguments.get("content", "")
            return call_obsidian_api(f"/vault/{path}", "POST", {"content": content}, is_text=True)
            
        elif name == "vault_delete":
            path = arguments.get("path") or arguments.get("filename")
            if not path: raise KeyError("path")
            return call_obsidian_api(f"/vault/{path}", "DELETE")
            
        elif name == "search":
            query = arguments.get("query", "")
            logger.info(f"Busca inteligente por: {query}")
            
            results = []
            
            # 1. Baixa lista de arquivos (Rápido e confiável)
            all_files_response = call_obsidian_api("/vault/")
            files = all_files_response if isinstance(all_files_response, list) else all_files_response.get("files", [])
            
            # Extrai apenas os caminhos (nomes dos arquivos)
            file_paths = [f['path'] if isinstance(f, dict) else f for f in files]
            
            # --- NÍVEL 1: Busca por Nome (Fuzzy e Parcial) ---
            # Normaliza a query para minúsculo
            q_lower = query.lower()
            
            for path in file_paths:
                p_lower = str(path).lower()
                
                # A. Match direto (substring)
                p_clean = p_lower.replace("-", " ").replace("_", " ")
                
                score = 0
                if q_lower in p_clean:
                    score = 100 
                else:
                    score = difflib.SequenceMatcher(None, q_lower, p_clean).ratio() * 100
                
                if score > 60:
                    results.append({
                        "path": path, # Mudado de filename para path
                        "score": score,
                        "match_type": "filename"
                    })
            
            # Ordena pelos melhores resultados
            results.sort(key=lambda x: x['score'], reverse=True)
            
            # Se achou arquivos pelo nome, retorna eles (Top 5)
            if len(results) > 0:
                return results[:5]

            # --- NÍVEL 2: Busca por Conteúdo (Via Obsidian) ---
            # Se não achou nada pelo nome, pede pro Obsidian varrer o conteúdo dos arquivos
            logger.info("Nome não encontrado, tentando busca profunda no conteúdo...")
            try:
                return call_obsidian_api(
                    "/vault/search", 
                    method="POST", 
                    data={"content": query}, 
                    is_text=True
                )
            except:
                return {
                    "found": False, 
                    "message": f"Não encontrei nada parecido com '{query}' nem nos nomes, nem no conteúdo."
                }
            
        elif name == "get_daily_note":
            date = arguments.get("date")
            logger.info(f"Buscando nota diária para: {date}")
            
            # Obter lista de arquivos
            all_files_response = call_obsidian_api("/vault/")
            logger.info(f"Resposta completa de /vault/: {all_files_response}")
            
            # Extrair lista de arquivos da resposta
            file_list = all_files_response.get("files", [])
            logger.info(f"Lista de arquivos: {file_list}")
            
            # Padrões de nome de arquivo possíveis
            patterns = [
                f"{date}.md",
                f"Daily Notes/{date}.md",
                f"Diário/{date}.md",
                f"{date.replace('-', '')}.md",
                f"{date.replace('-', '_')}.md"
            ]
            
            # Tenta encontrar um arquivo que corresponda a qualquer padrão
            for filename in file_list:
                for pattern in patterns:
                    if pattern in filename:  # Verifica se o padrão está contido no nome do arquivo
                        content = call_obsidian_api(f"/vault/{filename}")
                        return {
                            "found": True,
                            "filename": filename,
                            "content": content
                        }
            
            return {
                "found": False,
                "message": f"Arquivo diário para {date} não encontrado",
                "suggestions": f"Padrões testados: {patterns}",
                "all_files": file_list
            }
            
        elif name == "execute_command":
            command_id = arguments.get("command_id")
            return call_obsidian_api(f"/command/{command_id}", "POST")
            
        else:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
            
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing argument: {str(e)}")

@app.get("/health")
async def health_check():
    try:
        response = call_obsidian_api("/vault/")
        return {"status": "ok", "vault": bool(response)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)