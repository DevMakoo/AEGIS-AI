# AEGIS

Assistente pessoal inteligente para Windows, desenvolvida em Python.

O objetivo do AEGIS é conversar em português brasileiro, receber comandos digitados
e de voz, responder com síntese de voz, integrar-se a um modelo de IA, abrir
aplicativos autorizados, executar automações seguras e pré-definidas e oferecer uma
interface desktop personalizável — tudo sobre uma arquitetura modular e testável.

> **Estado atual: Fase 1 — fundação.** A aplicação inicializa, carrega configurações,
> registra logs (sem expor segredos) e encerra. Ainda não há voz, IA, interface
> gráfica nem automações.

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

Códigos de saída: `0` sucesso, `1` falha de inicialização, `2` configuração inválida.

Os logs ficam em `logs\aegis.log` (UTF-8). No Windows PowerShell 5.1, leia com:

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
app/          ponto de entrada (main.py) e inicialização (bootstrap.py)
core/         configuração, logging, exceções e estado da aplicação
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

- Loop de conversa por texto no terminal (comandos digitados).
- Integração com um modelo de IA.
- Síntese de voz e, depois, reconhecimento de voz.
- Abertura de aplicativos a partir de uma lista de permissões (allowlist).
- Automações pré-definidas e seguras — nunca comandos arbitrários.
- Histórico e memória com controle do usuário.
- Interface desktop futurista e personalizável.
