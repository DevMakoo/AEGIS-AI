"""Hierarquia de exceções do AEGIS."""


class AegisError(Exception):
    """Erro base de todas as exceções específicas do AEGIS."""


class ConfigError(AegisError):
    """Configuração ausente, inválida ou inconsistente."""


class StartupError(AegisError):
    """Falha ao inicializar a aplicação."""


class InvalidStateTransitionError(AegisError):
    """Transição de estado da aplicação não permitida."""
