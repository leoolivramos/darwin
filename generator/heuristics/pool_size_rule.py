import os
import re

from heuristics.base import RuleNotApplicable
from utils.fs import iter_java_files, read_text, relpath

_POOL_PATTERN = re.compile(r'(\.(?:set(?:Max|Maximum|Core)?PoolSize)\()(\d+)(\))')

PROPERTIES_PATH = "src/main/resources/application.properties"
TOMCAT_THREADS_KEY = "server.tomcat.threads.max"
TOMCAT_DEFAULT_THREADS = 200  # default do Spring Boot / Tomcat


def apply_pool_size_rule(file_path: str, increase_ratio: float = 1.5) -> str:
    """
    Ajusta tamanho de pool de conexões/threads em código Java via regex.
    Detecta padrões como:
      - .setMaxPoolSize(10)
      - .setMaximumPoolSize(20)
      - .setCorePoolSize(5)
    Aplica um incremento configurável (default: 1.5x, min: 20).

    Levanta RuleNotApplicable se não houver nenhum pool alterável.
    """
    content = read_text(file_path)

    def replacer(match):
        new_val = max(20, int(int(match.group(2)) * increase_ratio))
        return f"{match.group(1)}{new_val}{match.group(3)}"

    modified = _POOL_PATTERN.sub(replacer, content)

    if modified == content:
        raise RuleNotApplicable(f"Nenhum pool ajustável encontrado em {file_path}")
    return modified


def apply_tomcat_threads(properties: str, increase_ratio: float = 1.5) -> str:
    """
    Ajusta `server.tomcat.threads.max` em application.properties.
    Se a chave não existir, parte do default do Tomcat (200).
    """
    line_re = re.compile(rf'^(\s*{re.escape(TOMCAT_THREADS_KEY)}\s*=\s*)(\d+)\s*$', re.MULTILINE)
    match = line_re.search(properties)
    if match:
        new_val = int(int(match.group(2)) * increase_ratio)
        return line_re.sub(lambda m: f"{m.group(1)}{new_val}", properties, count=1)

    new_val = int(TOMCAT_DEFAULT_THREADS * increase_ratio)
    sep = "" if properties.endswith(("\n", "\r\n")) or not properties else "\n"
    return f"{properties}{sep}\n# Darwin: pool de threads do Tomcat ajustado\n{TOMCAT_THREADS_KEY}={new_val}\n"


def plan_pool_size(repo_path: str, file_path: str, hotspot: dict) -> dict:
    """Retorna {caminho_relativo: novo_conteúdo} com as mudanças da regra."""
    candidates = [file_path] + [f for f in iter_java_files(repo_path) if f != file_path]
    for candidate in candidates:
        try:
            return {relpath(repo_path, candidate): apply_pool_size_rule(candidate)}
        except RuleNotApplicable:
            continue

    props = os.path.join(repo_path, PROPERTIES_PATH)
    if os.path.exists(props):
        return {PROPERTIES_PATH: apply_tomcat_threads(read_text(props))}
    raise RuleNotApplicable("Nenhum pool de conexões/threads ajustável encontrado")
