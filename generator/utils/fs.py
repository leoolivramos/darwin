"""Helpers de filesystem para leitura/escrita robusta de código-fonte."""
import os
from typing import Iterator


def read_text(path: str) -> str:
    """Lê um arquivo texto preservando bytes inválidos em UTF-8 (surrogateescape)."""
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    """Escreve texto sem converter quebras de linha e preservando bytes originais."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(content)


def iter_java_files(repo_path: str) -> Iterator[str]:
    """Itera sobre os arquivos .java de produção (src/main/java) do repositório."""
    root = os.path.join(repo_path, "src", "main", "java")
    for dirpath, _, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(".java"):
                yield os.path.join(dirpath, name)


def relpath(repo_path: str, path: str) -> str:
    """Caminho relativo ao repositório, sempre com '/' como separador."""
    return os.path.relpath(path, repo_path).replace(os.sep, "/")
