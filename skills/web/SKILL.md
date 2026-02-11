# Skill: Navegação Web (via CLI)

## Descrição
Esta habilidade permite que o agente acesse informações na internet através de ferramentas de linha de comando. Como o agente roda localmente, ele tem acesso à rede do host.

## Ferramentas
Use `execute_shell` para invocar comandos de rede.

## Instruções e Capacidades

### 1. Pesquisa na Web (Grátis e Sem Chave)
Use a versão HTML do DuckDuckGo para buscar links e informações:
```bash
curl -s -L "https://duckduckgo.com/html/?q=termo+de+busca" | grep "result__snippet" -A 2 | head -n 20
```
*Este método funciona sem autenticação e retorna trechos dos sites encontrados.*

### 2. Leitura de Conteúdo (Reader)
Para ler o conteúdo de um link específico (obtido no passo 1) em formato texto:
```bash
curl -s "https://r.jina.ai/https://url-do-site.com"
```
*(O r.jina.ai ainda é gratuito para leitura de URLs individuais).*
*(Nota: O prefixo r.jina.ai converte qualquer site em Markdown limpo, ideal para o contexto da IA).*

### 3. Verificar Conectividade
```bash
ping -c 1 google.com
```

### 4. Obter Clima
```bash
curl -s "https://wttr.in/Sao_Paulo?format=3"
```

## Boas Práticas
- Prefira APIs que retornam JSON ou Markdown.
- Evite dar `curl` direto em sites com muito HTML/JS, pois vai poluir o contexto.
- Se o site for grande, use `| head -n 50` para ler apenas o início.
