"""Testes das heurísticas e do fluxo git do Generator contra o código real em app/."""
import os
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from heuristics.base import RuleNotApplicable
from heuristics.caching_rule import apply_caching_rule, plan_caching
from heuristics.pool_size_rule import apply_tomcat_threads, plan_pool_size
from heuristics.timeout_rule import plan_timeout
from utils.ast_parser import ASTParser
from utils.git_helper import GitHelper
from utils.guard import find_protected

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app")
CONTROLLER = "src/main/java/com/leonardoramos/app/controller/PerformanceController.java"


@pytest.fixture
def repo(tmp_path):
    """Cópia do código real da aplicação, sem histórico git."""
    dest = tmp_path / "repo"
    shutil.copytree(APP_DIR, dest, ignore=shutil.ignore_patterns("target", ".git"))
    return str(dest)


def test_ast_parser_finds_controller_by_endpoint_mapping(repo):
    path = ASTParser(repo).find_relevant_file({"endpoint": "/slow"})
    assert path.replace("\\", "/").endswith(CONTROLLER)


def test_ast_parser_falls_back_to_first_controller(repo):
    path = ASTParser(repo).find_relevant_file({"endpoint": "/does-not-exist"})
    assert path.replace("\\", "/").endswith(CONTROLLER)


def test_caching_targets_the_hotspot_endpoint(repo):
    controller = os.path.join(repo, CONTROLLER)
    modified = apply_caching_rule(controller, endpoint="/slow")
    lines = modified.splitlines()
    idx = next(i for i, line in enumerate(lines) if 'Cacheable("darwin-cache")' in line)
    assert '@GetMapping("/slow")' in lines[idx - 1]
    assert "simulateSlow" in lines[idx + 1]
    assert modified.count("Cacheable") == 1


def test_caching_plan_enables_cache_support(repo):
    changes = plan_caching(repo, os.path.join(repo, CONTROLLER), {"endpoint": "/slow"})
    assert CONTROLLER in changes
    assert "spring-boot-starter-cache" in changes["pom.xml"]
    app_file = next(k for k in changes if k.endswith("AppApplication.java"))
    assert "@org.springframework.cache.annotation.EnableCaching" in changes[app_file]


def test_caching_is_not_applied_twice(repo):
    controller = os.path.join(repo, CONTROLLER)
    with open(controller, "w", encoding="utf-8") as f:
        f.write('@Cacheable("x")\npublic class A {}')
    with pytest.raises(RuleNotApplicable):
        apply_caching_rule(controller, endpoint="/slow")


def test_timeout_and_pool_fall_back_correctly_for_the_real_app(repo):
    controller = os.path.join(repo, CONTROLLER)
    with pytest.raises(RuleNotApplicable):
        plan_timeout(repo, controller, {})

    changes = plan_pool_size(repo, controller, {})
    assert list(changes) == ["src/main/resources/application.properties"]
    assert "server.tomcat.threads.max=300" in changes["src/main/resources/application.properties"]


def test_tomcat_threads_updates_existing_value():
    out = apply_tomcat_threads("a=1\nserver.tomcat.threads.max=100\n", increase_ratio=2)
    assert "server.tomcat.threads.max=200" in out
    assert out.count("server.tomcat.threads.max") == 1


def test_guard_blocks_critical_files():
    assert find_protected(["src/main/java/x/SecurityConfig.java", "pom.xml"]) == ["src/main/java/x/SecurityConfig.java"]
    assert find_protected(["Dockerfile"]) == ["Dockerfile"]


# ── fluxo git: seed → branch candidato → promote → rollback ──────────────────

def test_git_flow_branch_promote_rollback(tmp_path):
    helper = GitHelper(repo_path=str(tmp_path / "repo"), source_path=APP_DIR)
    assert helper.has_commits()
    base = helper.head()

    changes = plan_caching(helper.repo_path, os.path.join(helper.repo_path, CONTROLLER), {"endpoint": "/slow"})
    result = helper.create_candidate_branch(changes, rule="caching", cycle_id="abc12345")
    assert result["branch"].startswith("darwin/caching_")
    assert "Cacheable" in result["diff"]
    assert helper.head() == base  # main continua intacta até a promoção

    promoted = helper.promote(result["branch"], "abc12345")
    assert promoted["previous_commit"] == base
    assert helper.head() == promoted["commit"] != base

    rolled = helper.rollback(promoted["commit"], "abc12345")
    assert rolled["reverted"] == promoted["commit"]
    content = subprocess.run(
        ["git", "-C", helper.repo_path, "show", f"HEAD:{CONTROLLER}"],
        capture_output=True, text=True, encoding="utf-8",
    ).stdout
    assert "Cacheable" not in content


def test_generator_api_generates_real_patch(tmp_path, monkeypatch, load_service):
    monkeypatch.setenv("REPO_PATH", str(tmp_path / "repo"))
    monkeypatch.setenv("APP_SOURCE_PATH", APP_DIR)
    generator = load_service("generator", "generator")
    client = TestClient(generator.app)

    assert client.get("/health").json()["repo_ready"] is True

    body = {"hotspots": [{"type": "latency", "endpoint": "/slow", "value": 3.0, "threshold": 2.0}], "cycle_id": "c1"}
    resp = client.post("/generate", json=body).json()
    assert resp["status"] == "success"
    assert resp["rule_applied"] == "caching"
    assert CONTROLLER in resp["files"]
    assert "Cacheable" in resp["diff"]

    # erro de negócio: nenhum timeout ajustável no app real
    body["hotspots"][0]["type"] = "error_rate"
    resp = client.post("/generate", json=body).json()
    assert resp["status"] == "no_applicable_rule"

    assert client.post("/generate", json={"hotspots": []}).status_code == 400
