---
description: Comandos para buscar notas e texto dentro do Obsidian.
keywords: search, buscar, procurar, grep, find, localizar, pesquisar, query, consulta, encontrar
---

# Busca no Obsidian

## 1. Busca Profunda (Conteúdo) - Preferencial
Usa `grep` no sistema de arquivos para encontrar texto dentro das notas. Muito rápido.

```bash
# Requer variável de ambiente OBSIDIAN_VAULT_PATH
grep -r -i "termo de busca" "$OBSIDIAN_VAULT_PATH"
```
*O resultado será o caminho absoluto do arquivo. Use `read_file` nesse caminho para ler.*

## 2. Busca de Arquivos (Nomes) - Via API
Se não tiver acesso direto ao disco, use a API para listar e filtrar.

```bash
curl -k -s -X GET "https://127.0.0.1:27124/vault/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" > files.json && grep -i "termo" files.json
```
