# Skill: Terminal do Sistema

## Descrição
Esta skill concede a você a capacidade de executar comandos shell no sistema local. Este é o seu método principal para interagir com o ambiente, executar scripts e invocar ferramentas CLI (como `curl`, `git`, `obsidian-cli`).

## Ferramentas
- `execute_shell`: Executa um comando bash e retorna stdout/stderr.

## Boas Práticas
1.  **Segurança em Primeiro Lugar**: Verifique os comandos antes de executar. Evite comandos destrutivos (`rm -rf`) a menos que explicitamente solicitado e verificado.
2.  **Tratamento de Saída**: Para comandos com saídas grandes, considere usar pipes para `head`, `tail` ou `grep` para evitar sobrecarregar a janela de contexto.
3.  **Não-Interativo**: Sempre execute comandos em modo não-interativo. Não execute comandos que esperem por entrada do usuário (como `nano`, `vim`, `python` REPL).
4.  **Encadeamento**: Você pode encadear comandos usando `&&` ou `;`, mas mantenha-os legíveis.

## Exemplos

### Listar Arquivos
```bash
ls -F
```

### Verificar Variáveis de Ambiente
```bash
printenv OBSIDIAN_API_TOKEN
```

### Requisição de Rede (curl)
```bash
curl -I https://google.com
```