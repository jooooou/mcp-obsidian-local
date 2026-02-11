---
description: Comandos para controlar a interface do Obsidian (abrir arquivos, rodar comandos).
keywords: open, abrir, command, palette, interface, ui
---

# Controle do Obsidian

## 1. Abrir Arquivo na Interface
Faz o Obsidian do usuário pular para a nota especificada.
```bash
curl -k -X POST "https://127.0.0.1:27124/open/Pasta/Minha%20Nota.md" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

## 2. Listar Comandos Disponíveis
Útil para descobrir IDs de comandos internos (ex: toggle-bold, split-pane).
```bash
curl -k -X GET "https://127.0.0.1:27124/commands/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

## 3. Executar Comando Interno
```bash
# Exemplo: Alternar Negrito
curl -k -X POST "https://127.0.0.1:27124/commands/editor:toggle-bold/" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```
