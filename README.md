# AEGIS

Assistente pessoal inteligente para Windows, desenvolvida em Python.

O objetivo do AEGIS é conversar em português brasileiro, receber comandos digitados
e de voz, responder com síntese de voz, integrar-se a um modelo de IA, abrir
aplicativos autorizados, executar automações seguras e pré-definidas e oferecer uma
interface desktop personalizável — tudo sobre uma arquitetura modular e testável.

> **Estado atual: Fase 2 — conversa por texto.** O AEGIS abre uma sessão interativa no
> terminal e responde a um conjunto fixo de comandos autorizados. Ainda não há voz,
> IA, interface gráfica nem automações.

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
ou por um arquivo `.env` na raiz (as variáveis do processo têm prioridade):

```powershell
Copy-Item .env.example .env
```

| Variável            | Padrão        | Valores                                   |
|---------------------|---------------|-------------------------------------------|
| `AEGIS_ENV`         | `development` | `development`, `test`, `production`       |
| `AEGIS_LOG_LEVEL`   | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `AEGIS_LOG_DIR`     | `logs`        | caminho relativo à raiz ou absoluto       |
| `AEGIS_LOG_TO_FILE` | `true`        | `true` / `false`                          |
| `AEGIS_LANGUAGE`    | `pt-BR`       | `pt-BR`                                   |
| `AEGIS_AI_API_KEY`  | *(vazio)*     | reservado para fase futura                |

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
Digite "ajuda" para conhecer os comandos disponíveis.

Você: status

AEGIS: Estou funcionando normalmente.
- Versão: 0.1.0
- Estado: em execução
- Sessão ativa há menos de um minuto
- Comandos atendidos nesta sessão: 0

Você: que horas são?

AEGIS: Agora são 14:05.

Você: sair

AEGIS: Encerrando a sessão. Até logo!
```

A sessão também termina com `Ctrl+Z` + `Enter` (fim da entrada) ou `Ctrl+C`.

Códigos de saída: `0` sucesso, `1` falha de inicialização, `2` configuração inválida,
`130` interrompido por `Ctrl+C` fora da leitura de entrada.

## Comandos disponíveis

| Comando  | O que faz                                  | Aliases                                |
|----------|--------------------------------------------|----------------------------------------|
| `ajuda`  | Lista os comandos e suas descrições        | `comandos`, `lista de comandos`        |
| `status` | Versão, estado, tempo de sessão e comandos atendidos | `estado`, `como você está`   |
| `hora`   | Hora local do sistema                      | `horas`, `que horas são`               |
| `data`   | Data local, por extenso em português       | `dia`, `que dia é hoje`                |
| `sair`   | Encerra a sessão                           | `encerrar`, `tchau`, `até logo`        |

Como a entrada é interpretada:

- Maiúsculas/minúsculas, acentos, espaços extras e pontuação final (`.`, `!`, `?`)
  são ignorados: `  QUE horas SAO? ` equivale a `hora`.
- Fora isso, a correspondência é **exata** — não há correção aproximada. `ajud`,
  `ajuda agora` ou `ajuda; sair` não são reconhecidos.
- Somente comandos do registro (`core/command_handlers.py`) são executados. Nenhuma
  entrada é avaliada como código Python, shell, PowerShell ou caminho de programa.

### Adicionando um comando (para desenvolvedores)

Crie a função em `core/command_handlers.py`, que recebe um `CommandContext` e retorna
o texto da resposta, e inclua um `Command` em `DEFAULT_COMMANDS`. O registro recusa
nomes duplicados e aliases conflitantes já na inicialização.

## Logs

O terminal mostra apenas avisos e erros; o registro completo vai para `logs\aegis.log`
(UTF-8). São registrados início/fim da aplicação e da sessão e o nome dos comandos
reconhecidos — o texto digitado não é gravado (entradas desconhecidas aparecem só
com o tamanho). No Windows PowerShell 5.1, leia com:

```powershell
Get-Content logs\aegis.log -Encoding utf8
```

## Testes e lint

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Os testes não usam internet, chaves de API nem alteram o Windows.

## Estrutura

```
app/          ponto de entrada (main.py), inicialização (bootstrap.py)
              e interface de terminal (terminal.py)
core/         configuração, logging, exceções, estado da aplicação,
              comandos (command*.py) e sessão de conversa (conversation.py)
ai/           integração com IA            (fase futura)
voice/        voz: reconhecimento e síntese (fase futura)
interface/    interface desktop            (fase futura)
automation/   automações seguras           (fase futura)
memory/       histórico e memória          (fase futura)
tests/        testes automatizados (pytest)
logs/         logs gerados (ignorados pelo Git)
main.py       atalho de execução
```

## Próximas funcionalidades

- Integração com um modelo de IA.
- Síntese de voz e, depois, reconhecimento de voz.
- Abertura de aplicativos a partir de uma lista de permissões (allowlist).
- Automações pré-definidas e seguras — nunca comandos arbitrários.
- Histórico e memória com controle do usuário.
- Interface desktop futurista e personalizável.
