---
description: Sistema de Notas e Arquivos Pessoais (Obsidian Vault). Use para acessar todo o conhecimento armazenado localmente, documentos e anotações.
keywords: obsidian, notas, knowledge base, pkm, arquivos, documentos
---

# Skill: Obsidian (Índice)

Esta skill permite interagir com o Obsidian via API REST Local e Shell.
As capacidades estão divididas em módulos:

- `skills/obsidian/read.md`: Ler notas, listar arquivos, ver nota ativa.
- `skills/obsidian/write.md`: Criar notas, editar, adicionar texto (append).
- `skills/obsidian/search.md`: Buscar texto dentro do vault (grep).
- `skills/obsidian/control.md`: Controlar a interface (abrir notas, rodar comandos).

**Pré-requisitos Gerais:**
- Plugin "Local REST API" ativo.
- Token `OBSIDIAN_API_TOKEN` configurado.
- URL base: `https://127.0.0.1:27124` (Use `curl -k`).
