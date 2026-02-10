class BiBotError(Exception):
    """基础异常"""


class TokenValidationError(BiBotError):
    """Token验证失败"""


class TokenFormatError(TokenValidationError):
    """Token格式错误"""


class TokenInvalidError(TokenValidationError):
    """Token无效（API验证失败）"""


class TokenDuplicateError(TokenValidationError):
    """Token已被注册"""


class TokenLimitError(TokenValidationError):
    """超出注册数量限制"""


class RegistryError(BiBotError):
    """BotRegistry操作失败"""


class BroadcastError(BiBotError):
    """广播操作失败"""


class ForwardError(BiBotError):
    """转发操作失败"""
