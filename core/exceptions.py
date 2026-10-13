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


class AIError(AegisError):
    """Falha controlada da camada de IA. A mensagem é técnica (para logs), não para o usuário."""


class AIConfigurationError(AIError):
    """IA habilitada, mas com configuração incompleta ou provedor sem implementação."""


class AIUnavailableError(AIError):
    """Servidor do provedor inacessível (ex.: Ollama parado ou não instalado)."""


class AIModelNotFoundError(AIError):
    """O modelo configurado não existe no provedor."""


class AIEndpointNotFoundError(AIError):
    """O endereço respondeu 404 sem indicar modelo ausente (URL errada ou outro serviço)."""


class AITimeoutError(AIError):
    """O provedor não respondeu dentro do tempo limite."""


class AIResponseError(AIError):
    """Erro HTTP ou resposta malformada do provedor."""


class AIProviderError(AIError):
    """Falha inesperada dentro do provedor."""
