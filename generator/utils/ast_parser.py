import os
import re
from typing import Optional

from utils.fs import iter_java_files, read_text
from utils.logger import get_logger

logger = get_logger("ast")

_CONTROLLER_MARKERS = ("@RestController", "@Controller")


class ASTParser:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def find_relevant_file(self, hotspot: dict) -> Optional[str]:
        """
        Localiza o arquivo Java responsável pelo endpoint do hotspot.

        Ordem de busca:
          1. Arquivo que mapeia o endpoint (@GetMapping("/slow"), @RequestMapping(...), etc.)
          2. Arquivo cujo nome contém o último segmento do endpoint (/api/user -> User*.java)
          3. Primeiro controller encontrado no projeto
        """
        endpoint = (hotspot.get("endpoint") or "").strip()
        java_files = list(iter_java_files(self.repo_path))

        if endpoint.startswith("/"):
            mapping = re.compile(r'Mapping\(\s*(?:(?:value|path)\s*=\s*)?\{?\s*"' + re.escape(endpoint) + r'"')
            for path in java_files:
                if mapping.search(read_text(path)):
                    logger.info(f"🔍 Arquivo que mapeia {endpoint}: {path}")
                    return path

            keyword = endpoint.split("/")[-1].capitalize()
            if keyword:
                for path in java_files:
                    if keyword in os.path.basename(path):
                        logger.info(f"🔍 Arquivo relevante por nome: {path}")
                        return path

        for path in java_files:
            if any(marker in read_text(path) for marker in _CONTROLLER_MARKERS):
                logger.info(f"🔍 Usando primeiro controller encontrado: {path}")
                return path

        return None
