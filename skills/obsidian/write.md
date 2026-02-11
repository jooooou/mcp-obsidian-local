---
description: Comandos para CRIAR, EDITAR e anexar texto a notas.
keywords: write, criar, edit, editar, append, adicionar, put, post
---

# Escrita no Obsidian

## 1. Criar ou Sobrescrever Nota (PUT)
**CUIDADO:** Isso apaga o conteúdo anterior se a nota existir.
```bash
curl -k -X PUT "https://127.0.0.1:27124/vault/NovaNota.md" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" 
  -H "Content-Type: text/markdown" 
  --data "Conteúdo da nota aqui."
```

## 2. Adicionar ao Final (Append) (POST)
Seguro para logs e anotações incrementais. Adiciona ao fim do arquivo.
```bash
# Use echo -e para garantir quebras de linha (
)
echo -e "

## Novo Tópico
Texto adicionado." | curl -k -X POST "https://127.0.0.1:27124/vault/MinhaNota.md" 
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" 
  -H "Content-Type: text/markdown" 
  --data-binary @-
```
