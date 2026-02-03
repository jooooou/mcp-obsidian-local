# Skill: Obsidian

## Descrição
Esta skill permite interagir com uma instância do Obsidian em execução através da sua API REST Local. Você pode ler notas, criar notas, buscar, executar comandos e navegar na interface.

## Pré-requisitos
- O Obsidian deve estar aberto.
- O plugin "Local REST API" deve estar instalado e ativo.
- A variável de ambiente `OBSIDIAN_API_TOKEN` deve estar configurada.
- A URL base é `https://127.0.0.1:27124`.
- **Importante:** O servidor usa certificado auto-assinado. Use sempre `curl -k` (ou `--insecure`).

## Ferramentas
Use a ferramenta `execute_shell` para rodar os comandos `curl`.

## Capacidades e Instruções

### 1. Obter Arquivo Ativo (Contexto)
Para ver qual nota está aberta na tela do usuário agora:

```bash
curl -k -X GET "https://127.0.0.1:27124/active/" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" \
  -H "Accept: application/vnd.olra.json"
```

### 2. Listar Arquivos (Vault)
Para listar todos os arquivos na raiz do cofre:

```bash
curl -k -X GET "https://127.0.0.1:27124/vault/" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```
*Use subpastas se necessário, ex: `/vault/Pasta/`.*

### 3. Ler uma Nota
Para ler o conteúdo de uma nota específica:

```bash
# Nota: Use %20 para substituir espaços no nome do arquivo!
curl -k -X GET "https://127.0.0.1:27124/vault/Pasta/Minha%20Nota.md" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

### 4. Criar ou Atualizar Nota (Sobrescrever)
Para escrever conteúdo em uma nota (substitui tudo):

```bash
curl -k -X PUT "https://127.0.0.1:27124/vault/NovaNota.md" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" \
  -H "Content-Type: text/markdown" \
  --data "Este é o conteúdo da nota."
```

### 5. Adicionar ao Final (Append)
Para adicionar texto ao final de uma nota existente sem quebrar a formatação:

```bash
# Use este formato para garantir que as quebras de linha (\n) funcionem:
echo -e "\n\nTexto para adicionar" | curl -k -X POST "https://127.0.0.1:27124/vault/MinhaNota.md" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" \
  -H "Content-Type: text/markdown" \
  --data-binary @-
```

### 6. Busca (Search)
**Método Preferencial (Busca Profunda):**
Se a variável `OBSIDIAN_VAULT_PATH` estiver definida, use `grep` para buscar dentro dos arquivos (rápido e confiável).

```bash
grep -r -i "termo de busca" "$OBSIDIAN_VAULT_PATH"
```
*Dica: O grep retornará o caminho absoluto do arquivo (ex: `/home/user/vault/Nota.md`). Copie e cole esse caminho EXATO na ferramenta `read_file`.*

**Método Alternativo (Via API - Apenas Nomes):**
Se não tiver acesso ao disco, use a API para listar arquivos e filtre o JSON.

1. Listar:
```bash
curl -k -s -X GET "https://127.0.0.1:27124/vault/" -H "Authorization: Bearer $OBSIDIAN_API_TOKEN" > files.json
```
2. Filtrar:
```bash
grep -i "termo" files.json
```


### 7. Listar Comandos
Para ver todos os comandos disponíveis no Obsidian (útil para descobrir IDs):

```bash
curl -k -X GET "https://127.0.0.1:27124/commands/" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

### 8. Executar Comando
Para disparar um comando interno (ex: negrito, abrir graph view):

```bash
curl -k -X POST "https://127.0.0.1:27124/commands/editor:toggle-bold/" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

### 9. Abrir Arquivo na Interface
Para fazer o Obsidian navegar até uma nota específica:

```bash
# Lembre-se do %20 para espaços
curl -k -X POST "https://127.0.0.1:27124/open/Pasta/Minha%20Nota.md" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

### 10. Nota Diária
Para pegar a Nota Diária atual (Daily Note):

```bash
curl -k -X GET "https://127.0.0.1:27124/periodic/daily/" \
  -H "Authorization: Bearer $OBSIDIAN_API_TOKEN"
```

## Tratamento de Erros
- **Connection Refused:** O Obsidian está fechado.
- **401 Unauthorized:** Token incorreto. Verifique `$OBSIDIAN_API_TOKEN`.
- **404 Not Found:** Arquivo não existe.
- **URL Malformed:** Verifique se usou `%20` nos espaços.