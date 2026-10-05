import os
import re
from typing import Optional

from heuristics.base import RuleNotApplicable
from utils.fs import iter_java_files, read_text, relpath

CACHEABLE = '@org.springframework.cache.annotation.Cacheable("darwin-cache")'
ENABLE_CACHING = "@org.springframework.cache.annotation.EnableCaching"

CACHE_DEPENDENCY = """        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-cache</artifactId>
        </dependency>
"""

_READ_METHOD_PATTERN = re.compile(
    r'(\n[ \t]*)(public\s+[\w<>,\[\]\s]+\s+(?:get|find|search|load|fetch)\w*\s*\()'
)


def apply_caching_rule(file_path: str, endpoint: Optional[str] = None) -> str:
    """
    Injeta @Cacheable (Spring) em um método de leitura que ainda não é cacheado.

    1. Se `endpoint` for informado, procura o método anotado com
       @GetMapping("<endpoint>") e o torna cacheável.
    2. Caso contrário (ou se não achar), procura métodos get/find/search/load/fetch.

    Levanta RuleNotApplicable se nada puder ser cacheado.
    """
    content = read_text(file_path)

    if "Cacheable" in content:
        raise RuleNotApplicable(f"{file_path} já possui cache")

    if endpoint:
        mapping = re.compile(
            r'(\n([ \t]*)@GetMapping\(\s*(?:(?:value|path)\s*=\s*)?"' + re.escape(endpoint) + r'"[^)]*\)[ \t]*)'
        )
        match = mapping.search(content)
        if match:
            indent = match.group(2)
            return content[:match.end()] + f"\n{indent}{CACHEABLE}" + content[match.end():]

    modified, count = _READ_METHOD_PATTERN.subn(
        lambda m: f"{m.group(1)}{CACHEABLE}{m.group(1)}{m.group(2)}", content, count=1
    )
    if count == 0:
        raise RuleNotApplicable(f"Nenhum método de leitura cacheável encontrado em {file_path}")
    return modified


def _add_cache_dependency(pom: str) -> str:
    if "spring-boot-starter-cache" in pom:
        return pom
    return pom.replace("    </dependencies>", CACHE_DEPENDENCY + "    </dependencies>", 1)


def _enable_caching(app_source: str) -> str:
    if "EnableCaching" in app_source:
        return app_source
    return app_source.replace("@SpringBootApplication", f"{ENABLE_CACHING}\n@SpringBootApplication", 1)


def cache_support_changes(repo_path: str) -> dict:
    """Mudanças de infraestrutura para que o @Cacheable tenha efeito (pom + @EnableCaching)."""
    changes = {}

    pom_path = os.path.join(repo_path, "pom.xml")
    if os.path.exists(pom_path):
        pom = read_text(pom_path)
        new_pom = _add_cache_dependency(pom)
        if new_pom != pom:
            changes["pom.xml"] = new_pom

    for java in iter_java_files(repo_path):
        source = read_text(java)
        if "@SpringBootApplication" in source:
            new_source = _enable_caching(source)
            if new_source != source:
                changes[relpath(repo_path, java)] = new_source
            break

    return changes


def plan_caching(repo_path: str, file_path: str, hotspot: dict) -> dict:
    """Retorna {caminho_relativo: novo_conteúdo} com as mudanças da regra."""
    modified = apply_caching_rule(file_path, endpoint=hotspot.get("endpoint"))
    changes = {relpath(repo_path, file_path): modified}
    changes.update(cache_support_changes(repo_path))
    return changes
