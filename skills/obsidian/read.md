---
description: Comandos para LER notas, listar arquivos e obter contexto atual.
keywords: read, ler, listar, cat, ls, active, daily, current
---

# Leitura no Obsidian

## 1. Ler uma Nota Específica
```bash
# Use %20 para espaços na URL
curl -k -X GET "https://127.0.0.1:27124/vault/Pasta/Minha%20Nota.md" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

## 2. Obter Nota Ativa (O que estou vendo?)
Retorna metadados da nota aberta atualmente na interface.
```bash
curl -k -X GET "https://127.0.0.1:27124/active/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" 
  -H "Accept: application/vnd.olra.json"
```

## 3. Listar Todos os Arquivos
```bash
curl -k -X GET "https://127.0.0.1:27124/vault/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

## 4. Ler Nota Diária (Daily Note)
```bash
curl -k -X GET "https://127.0.0.1:27124/periodic/daily/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```
