"""Hierarquia de exceções do AEGIS."""


class AegisError(Exception):
    """Erro base de todas as exceções específicas do AEGIS."""


class ConfigError(AegisError):
    """Configuração ausente, inválida ou inconsistente."""


class StartupError(AegisError):
    """Falha ao inicializar a aplicação."""


class InvalidStateTransitionError(AegisError):
    """Transição de estado da aplicação não permitida."""


class CommandRegistrationError(AegisError):
    """Comando inválido ou em conflito com outro já registrado."""


class CommandError(AegisError):
    """Falha esperada durante a execução de um comando, com mensagem para o usuário."""


class SessionClosedError(AegisError):
    """Tentativa de usar uma sessão de conversa já encerrada."""
