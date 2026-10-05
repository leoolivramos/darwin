import re

from heuristics.base import RuleNotApplicable
from utils.fs import read_text, relpath

_TIMEOUT_PATTERN = re.compile(r'(\.(?:set(?:Connect|Read)?Timeout)\()(\d+)(\))')


def apply_timeout_rule(file_path: str, factor: float = 0.75) -> str:
    """
    Ajusta valores de timeout em código Java via regex.
    Detecta padrões como:
      - .setTimeout(2000)
      - .setConnectTimeout(5000)
      - .setReadTimeout(10000)
    Aplica um fator de redução (default: 0.75, ou seja, 25% de redução).

    Levanta RuleNotApplicable se não houver nenhum timeout alterável.
    """
    content = read_text(file_path)

    def replacer(match):
        new_val = max(100, int(int(match.group(2)) * factor))
        return f"{match.group(1)}{new_val}{match.group(3)}"

    modified = _TIMEOUT_PATTERN.sub(replacer, content)

    if modified == content:
        raise RuleNotApplicable(
            f"Nenhum timeout ajustável encontrado em {file_path}"
        )
    return modified


def plan_timeout(repo_path: str, file_path: str, hotspot: dict) -> dict:
    """Retorna {caminho_relativo: novo_conteúdo} com as mudanças da regra."""
    from utils.fs import iter_java_files

    candidates = [file_path] + [f for f in iter_java_files(repo_path) if f != file_path]
    for candidate in candidates:
        try:
            return {relpath(repo_path, candidate): apply_timeout_rule(candidate)}
        except RuleNotApplicable:
            continue
    raise RuleNotApplicable("Nenhum arquivo Java possui chamadas de timeout ajustáveis")
