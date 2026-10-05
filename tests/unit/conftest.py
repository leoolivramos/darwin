"""
conftest.py — configura sys.path para que os testes unitários possam importar
módulos dos serviços (detector, generator, evaluator, orchestrator) diretamente,
replicando o ambiente de execução dos containers Docker.
"""
import sys
import os

# Adiciona cada pasta de serviço ao sys.path para permitir imports diretos
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for svc in ["detector", "generator", "evaluator", "orchestrator"]:
    svc_path = os.path.join(_base, svc)
    if svc_path not in sys.path:
        sys.path.insert(0, svc_path)


import importlib

import pytest

_CLASHING = ("models", "state", "tasks", "worker", "audit", "storage")


@pytest.fixture
def load_service():
    """
    Importa o módulo principal de um serviço isolando módulos com nomes iguais
    (models, state, ...) que existem em vários serviços.
    Uso: generator = load_service("generator", "generator")
    """
    added = []

    def _load(service: str, module: str):
        path = os.path.join(os.path.dirname(_base), service)
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k in _CLASHING or k == module}
        sys.path.insert(0, path)
        added.append((path, saved))
        return importlib.import_module(module)

    yield _load

    for path, saved in reversed(added):
        if path in sys.path:
            sys.path.remove(path)
        for k in list(sys.modules):
            if k in _CLASHING:
                sys.modules.pop(k)
        sys.modules.update(saved)
