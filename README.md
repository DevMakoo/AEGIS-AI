# AEGIS

Assistente pessoal inteligente para Windows, desenvolvida em Python.

O objetivo do AEGIS é conversar em português brasileiro, receber comandos digitados
e de voz, responder com síntese de voz, integrar-se a um modelo de IA, abrir
aplicativos autorizados, executar automações seguras e pré-definidas e oferecer uma
interface desktop personalizável — tudo sobre uma arquitetura modular e testável.

> **Estado atual: Fase 3 — conversa híbrida.** O AEGIS abre uma sessão no terminal,
> responde a comandos autorizados e, se habilitado, conversa em português usando um
> modelo local do [Ollama](https://ollama.com). A IA é **somente conversacional**: não
> executa nada no computador. Voz, interface gráfica, automação de aplicativos e
> memória persistente **não** fazem parte desta fase.

## Requisitos

- Windows 10/11 (64 bits)
- **Python 3.12.x (64 bits)**, acessível pelo launcher: `py -3.12 --version`
- Windows PowerShell 5.1 ou PowerShell 7

O projeto usa explicitamente `py -3.12`; não dependa da versão padrão de `python`.

## Preparação do ambiente

Todos os comandos abaixo são para PowerShell, executados **na raiz do projeto**.
O caminho contém espaço, então use aspas:

```powershell
cd "C:\dev\A.E.G.I.S\AEGIS IA"
```

### 1. Criar a `.venv`

```powershell
py -3.12 -m venv .venv
```

### 2. Ativar a `.venv`

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a execução de scripts, libere apenas para o usuário atual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Para desativar: `deactivate`.

### 3. Instalar as dependências

```powershell
# Somente execução
python -m pip install -r requirements.txt

# Desenvolvimento e testes (inclui as de execução)
python -m pip install -r requirements-dev.txt
```

### 4. Configuração (opcional)

As configurações têm valores padrão e podem ser alteradas por variáveis de ambiente
ou por um arquivo `.env` na raiz:

```powershell
Copy-Item .env.example .env
```

**Precedência** (a mesma regra do `python-dotenv` sem `override`):

| `.env` | Variável do processo | Resultado |
|---|---|---|
| `AEGIS_AI_ENABLED=true` | *(ausente)* | `true` (vale o `.env`) |
| `AEGIS_AI_ENABLED=true` | `false` | `false` (o processo prevalece) |
| `AEGIS_AI_ENABLED=true` | *(presente, mas vazia)* | `false` — o padrão: uma variável presente no processo prevalece mesmo vazia, e vazio significa "usar o padrão" |
| `AEGIS_AI_ENABLED=` | *(ausente)* | `false` (padrão) |

No PowerShell, `$env:AEGIS_AI_ENABLED = ""` **remove** a variável do processo (então
o `.env` volta a valer). Variáveis vazias no processo costumam vir de outros shells
ou de configurações de execução de IDEs.

| Variável            | Padrão        | Valores                                   |
|---------------------|---------------|-------------------------------------------|
| `AEGIS_ENV`         | `development` | `development`, `test`, `production`       |
| `AEGIS_LOG_LEVEL`   | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `AEGIS_LOG_DIR`     | `logs`        | caminho relativo à raiz ou absoluto       |
| `AEGIS_LOG_TO_FILE` | `true`        | `true` / `false`                          |
| `AEGIS_LANGUAGE`    | `pt-BR`       | `pt-BR`                                   |
| `AEGIS_AI_API_KEY`  | *(vazio)*     | reservado para provedor online futuro     |

As variáveis da IA estão na seção [Conversa inteligente](#conversa-inteligente-ia).
Valores inválidos impedem a inicialização com uma mensagem clara (código de saída `2`).

O arquivo `.env` nunca deve ser versionado. Valores secretos são mascarados em
`repr` e substituídos por `***REDACTED***` nos logs.

## Executar

Com a `.venv` ativada:

```powershell
python main.py
```

Ou sem ativar:

```powershell
.\.venv\Scripts\python.exe main.py
```

Exemplo de sessão:

```text
AEGIS v0.1.0
Sistema inicializado.
Conversa inteligente: desativada (AEGIS_AI_ENABLED=false).
Digite "ajuda" para conhecer os comandos disponíveis.

Você: status

AEGIS: Estou funcionando normalmente.
- Versão: 0.1.0
- Estado: em execução
- Sessão ativa há menos de um minuto
- Comandos atendidos nesta sessão: 0
- Conversa inteligente: desativada (AEGIS_AI_ENABLED=false)

Você: que horas são?

AEGIS: Agora são 14:05.

Você: sair

AEGIS: Encerrando a sessão. Até logo!
```

A sessão também termina com `Ctrl+Z` + `Enter` (fim da entrada) ou `Ctrl+C` no
prompt `Você:`. Um `Ctrl+C` enquanto o AEGIS processa uma mensagem (por exemplo,
aguardando a IA) cancela **só aquela resposta** e a sessão continua — veja a
limitação no Windows em [Limitações conhecidas](#limitações-conhecidas).

Códigos de saída: `0` sucesso, `1` falha de inicialização, `2` configuração inválida,
`130` interrompido por `Ctrl+C` fora da leitura de entrada.

## Comandos disponíveis

| Comando  | O que faz                                  | Aliases                                |
|----------|--------------------------------------------|----------------------------------------|
| `ajuda`  | Lista os comandos e suas descrições        | `comandos`, `lista de comandos`        |
| `status` | Versão, estado, sessão, comandos e estado da IA | `estado`                |
| `hora`   | Hora local do sistema                      | `horas`, `que horas são`               |
| `data`   | Data local, por extenso em português       | `dia`, `que dia é hoje`                |
| `sair`   | Encerra a sessão                           | `encerrar`                             |

Frases naturais como "como você está", "tchau" ou "até logo" **não** são comandos:
com a IA habilitada elas fazem parte da conversa (e não encerram a sessão). Para
sair, use `sair` ou `encerrar`.

Como a entrada é interpretada:

- Maiúsculas/minúsculas, acentos, espaços extras e pontuação final (`.`, `!`, `?`)
  são ignorados: `  QUE horas SAO? ` equivale a `hora`.
- Fora isso, a correspondência é **exata** — não há correção aproximada. `ajud`,
  `ajuda agora` ou `ajuda; sair` não são reconhecidos.
- Somente comandos do registro (`core/command_handlers.py`) são executados. Nenhuma
  entrada é avaliada como código Python, shell, PowerShell ou caminho de programa.

Com a IA habilitada, o que **não** for um comando registrado vai para o modelo (veja
abaixo). Sem IA, o AEGIS responde que não reconheceu o comando.

### Adicionando um comando (para desenvolvedores)

Crie a função em `core/command_handlers.py`, que recebe um `CommandContext` e retorna
o texto da resposta, e inclua um `Command` em `DEFAULT_COMMANDS`. O registro recusa
nomes duplicados e aliases conflitantes já na inicialização.

## Conversa inteligente (IA)

### Como funciona

```
entrada ──► comando registrado? ──sim──► handler autorizado ──► resposta
                    │ não
                    ▼
            IA habilitada? ──não──► "Não reconheci esse comando..."
                    │ sim
                    ▼
  AIService (histórico + mensagem de sistema) ──► AIProvider (Ollama) ──► texto
```

- **Comandos têm prioridade absoluta.** A IA nunca decide qual comando executar.
- A resposta do modelo é **apenas texto exibido**: nunca é avaliada como código, nunca
  executa programas e nunca é reprocessada como comando (se o modelo responder
  "sair", a sessão continua).
- Sequências de controle do terminal (ANSI etc.) são removidas da resposta.
- Falhas da IA geram uma mensagem curta; os comandos continuam funcionando.

Arquitetura (`ai/`):

| Arquivo | Responsabilidade |
|---|---|
| `provider.py` | Contrato `AIProvider` e `ChatMessage` |
| `ollama.py` | Provedor Ollama (`POST /api/chat`, sem streaming) |
| `factory.py` | Seleção do provedor pela configuração (ponto de extensão) |
| `service.py` | Contexto, chamada, validação, histórico e mensagens de erro |
| `history.py` | Histórico em memória, limitado, com mensagem de sistema preservada |
| `prompts.py` | Mensagem de sistema padrão do AEGIS |

**Nenhuma dependência nova:** a comunicação HTTP usa `urllib`, da biblioteca padrão
do Python — uma única requisição local não justifica uma biblioteca externa.

Para adicionar um provedor no futuro (ex.: uma API online), basta implementar o
contrato `AIProvider`, incluir o nome em `AIProviderName` (`core/config.py`) e
registrá-lo em `ai/factory.py`. Nenhum provedor online existe nesta fase.

### Instalar e verificar o Ollama

O AEGIS **não** instala o Ollama, **não** baixa modelos e **não** inicia nem encerra
o servidor. Faça isso manualmente:

1. Instale o Ollama para Windows pelo site oficial: <https://ollama.com/download>
   (ou `winget install --id Ollama.Ollama -e`).
2. Confira a instalação e o servidor (o instalador o deixa em execução):

   ```powershell
   ollama --version
   Invoke-RestMethod http://127.0.0.1:11434/api/version
   ```

3. Baixe um modelo (download de alguns GB; escolha conforme sua memória RAM/VRAM):

   ```powershell
   ollama pull llama3.2
   ```

4. Liste os modelos instalados:

   ```powershell
   ollama list
   ```

### Configurar e iniciar

No `.env` (ou em variáveis de ambiente), use o **nome exato** exibido por `ollama list`:

```dotenv
AEGIS_AI_ENABLED=true
AEGIS_OLLAMA_MODEL=llama3.2
```

Ou só para a sessão atual do PowerShell:

```powershell
$env:AEGIS_AI_ENABLED = "true"
$env:AEGIS_OLLAMA_MODEL = "llama3.2"
.\.venv\Scripts\python.exe main.py
```

Para trocar de modelo, altere `AEGIS_OLLAMA_MODEL` e reinicie o AEGIS.

| Variável | Padrão | Descrição |
|---|---|---|
| `AEGIS_AI_ENABLED` | `false` | Liga a conversa por IA |
| `AEGIS_AI_PROVIDER` | `ollama` | Provedor; nesta fase só `ollama` (outro valor é erro de configuração) |
| `AEGIS_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Endereço do Ollama; só loopback, salvo autorização abaixo. Pode terminar em `/api` ou `/api/chat` (é normalizado) |
| `AEGIS_OLLAMA_ALLOW_REMOTE` | `false` | Permite um endereço fora deste computador |
| `AEGIS_OLLAMA_MODEL` | *(vazio)* | Modelo instalado; sem ele a IA fica indisponível |
| `AEGIS_AI_TIMEOUT_SECONDS` | `60` | Tempo limite por resposta (1 a 600) |
| `AEGIS_AI_MAX_HISTORY_MESSAGES` | `20` | Mensagens mantidas na sessão (2 a 200) |
| `AEGIS_AI_SYSTEM_PROMPT` | *(padrão)* | Mensagem de sistema personalizada |

### Rede e privacidade

- **Conexão direta:** o AEGIS ignora proxies do sistema (`HTTP_PROXY`, `HTTPS_PROXY`)
  e não segue redirecionamentos ao falar com o Ollama.
- **Somente local por padrão:** `AEGIS_OLLAMA_BASE_URL` precisa apontar para
  `localhost`, `127.x.x.x` ou `::1`. Outro endereço (ex.: um PC da rede) só é aceito
  com `AEGIS_OLLAMA_ALLOW_REMOTE=true` — nesse caso **suas mensagens saem deste
  computador**, sem criptografia se a URL for `http://`. URLs com usuário ou senha
  embutidos são recusadas.
- Não há provedor online nesta fase; nada é enviado a serviços na internet.
- O histórico existe **somente em memória** e é descartado ao encerrar a sessão.
  Nada da conversa é gravado em disco.
- Os logs registram apenas eventos, tamanhos e tipos de erro — não o conteúdo das
  mensagens.
- Valores secretos conhecidos da configuração (ex.: `AEGIS_AI_API_KEY`) são removidos
  antes do envio ao modelo. Isso **não** detecta outros dados sensíveis que você
  digitar: evite escrever senhas ou dados pessoais na conversa.

### Desabilitar a IA

Defina `AEGIS_AI_ENABLED=false` (ou remova a variável). Todos os comandos continuam
funcionando normalmente.

### Problemas comuns

| Mensagem do AEGIS | O que fazer |
|---|---|
| "Não consegui falar com o Ollama" | Verifique se o Ollama está aberto (`ollama list` deve responder). Se necessário, inicie-o pelo menu Iniciar ou com `ollama serve`. |
| "O modelo configurado não foi encontrado" | Confira `ollama list` e ajuste `AEGIS_OLLAMA_MODEL`, ou baixe-o com `ollama pull <modelo>`. |
| "O endereço configurado não respondeu como um servidor Ollama" | O endereço respondeu "não encontrado" sem mencionar modelo: confira `AEGIS_OLLAMA_BASE_URL` (porta e caminho) e se é mesmo o Ollama naquela porta. |
| "A IA demorou demais para responder" | O primeiro uso carrega o modelo e pode ser lento; tente de novo ou aumente `AEGIS_AI_TIMEOUT_SECONDS`. |
| "Conversa inteligente: indisponível (defina AEGIS_OLLAMA_MODEL)" | A IA está ligada sem modelo; configure `AEGIS_OLLAMA_MODEL`. |

O comando `status` mostra o estado da IA e, se a última tentativa falhou, o motivo
em português (ex.: "Ollama inacessível", "modelo não encontrado", "tempo limite
excedido"). Detalhes técnicos de falhas inesperadas vão apenas para o arquivo de log.

### Limitações conhecidas

- **Ctrl+C durante a espera da IA, no Windows:** o cancelamento só é processado
  quando a espera de rede termina — na prática, ao fim de `AEGIS_AI_TIMEOUT_SECONDS`
  (ou antes, se a resposta chegar). Isso foi medido: com tempo limite de 4 s e 8 s,
  o Ctrl+C teve efeito em 4,0 s e 8,0 s. É uma limitação do Windows (a espera do
  socket não é interrompida pelo Ctrl+C), não do `urllib` em si. Quando o
  cancelamento acontece, a conexão HTTP é fechada, nada entra no histórico e a
  sessão continua. Para reduzir a espera, diminua `AEGIS_AI_TIMEOUT_SECONDS`.
- Sem streaming: a resposta aparece inteira ao final, e o terminal fica aguardando
  sem indicador de progresso.
- O histórico é limitado por número de mensagens, não por tokens; mensagens muito
  longas podem exceder o contexto do modelo.
- O modelo pode errar ou inventar informações; ele não tem acesso à internet nem
  à hora e data reais (use os comandos `hora` e `data`).
- Não há novas tentativas automáticas: em caso de falha, envie a mensagem de novo.

## Logs

O terminal mostra apenas avisos e erros; o registro completo vai para `logs\aegis.log`
(UTF-8). São registrados início/fim da aplicação e da sessão e o nome dos comandos
reconhecidos e, com IA, provedor, modelo, duração e tipo de erro — o texto digitado
e as respostas da IA não são gravados (apenas os tamanhos). Falhas inesperadas do
provedor vão **somente para o arquivo**, com o tipo do erro e os locais da pilha
(arquivo, linha, função), sem a mensagem da exceção. Textos de erro devolvidos pelo
servidor são reduzidos a uma linha de caracteres imprimíveis, com no máximo 200
caracteres. No Windows PowerShell 5.1, leia com:

```powershell
Get-Content logs\aegis.log -Encoding utf8
```

## Testes e lint

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Os testes não usam internet, chaves de API nem servidor Ollama, e não alteram o
Windows. Todas as respostas e falhas do Ollama são simuladas (dublês em
`tests/helpers.py`), e uma proteção automática (`tests/conftest.py`) faz falhar
qualquer teste que tente abrir uma conexão via `http.client` — o transporte do
`urllib` e, portanto, do provedor Ollama (HTTP e HTTPS, ambos testados). Ela **não**
cobre sockets diretos nem bibliotecas com transporte próprio (ex.: `httpx`,
`requests`/`urllib3`).

## Estrutura

```
app/          ponto de entrada (main.py), inicialização (bootstrap.py)
              e interface de terminal (terminal.py)
core/         configuração, logging, exceções, estado da aplicação,
              comandos (command*.py) e sessão de conversa (conversation.py)
ai/           IA conversacional: contrato, provedor Ollama, serviço e histórico
voice/        voz: reconhecimento e síntese (fase futura)
interface/    interface desktop            (fase futura)
automation/   automações seguras           (fase futura)
memory/       histórico e memória          (fase futura)
tests/        testes automatizados (pytest)
logs/         logs gerados (ignorados pelo Git)
main.py       atalho de execução
```

## Próximas funcionalidades

- Síntese de voz e, depois, reconhecimento de voz.
- Abertura de aplicativos a partir de uma lista de permissões (allowlist).
- Automações pré-definidas e seguras — nunca comandos arbitrários.
- Histórico e memória com controle do usuário.
- Interface desktop futurista e personalizável.
