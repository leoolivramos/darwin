"""
Proteção de módulos críticos: patches automáticos nunca alteram estes arquivos.
Mudanças nesses caminhos exigem revisão humana.
"""
import fnmatch
import os

DEFAULT_PROTECTED = (
    "*/security/*,*Security*.java,*Auth*.java,*Credential*,*Password*,*Secret*,"
    "Dockerfile,.mvn/*,mvnw,mvnw.cmd"
)


def protected_patterns() -> list:
    raw = os.getenv("DARWIN_PROTECTED_PATHS", DEFAULT_PROTECTED)
    return [p.strip() for p in raw.split(",") if p.strip()]


def find_protected(paths) -> list:
    """Retorna os caminhos (relativos, com '/') que casam com algum padrão protegido."""
    patterns = protected_patterns()
    blocked = []
    for path in paths:
        norm = path.replace("\\", "/")
        name = norm.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(norm, p) or fnmatch.fnmatch(name, p) for p in patterns):
            blocked.append(path)
    return blocked
