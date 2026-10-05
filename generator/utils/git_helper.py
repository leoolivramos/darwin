import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from typing import Optional

from utils.fs import write_text
from utils.logger import get_logger

logger = get_logger("git")

MAIN_BRANCH = "main"
_SEED_IGNORE = shutil.ignore_patterns(".git", "target", ".idea", "*.iml", ".vscode", "HELP.md")


class GitError(RuntimeError):
    """Falha ao executar um comando git."""


class NoChanges(Exception):
    """O patch candidato não altera nenhum arquivo."""


class GitHelper:
    """
    Gerencia o repositório de código que o Darwin evolui.

    O repositório é semeado a partir do código-fonte da aplicação (APP_SOURCE_PATH)
    e cada patch vira um branch `darwin/*` com um commit real. A árvore de trabalho
    sempre volta para `main`, então o Sandbox pode ler qualquer branch via git.
    """

    def __init__(self, repo_path: str = "/repo", source_path: Optional[str] = None):
        self.repo_path = repo_path
        self.source_path = source_path or os.getenv("APP_SOURCE_PATH", "")
        self.lock = threading.RLock()
        os.makedirs(repo_path, exist_ok=True)
        self._ensure_git_repo()
        self.seed_from_source()

    # ── infraestrutura ────────────────────────────────────────────────────────
    def _git(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", "-C", self.repo_path, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if check and proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} falhou: {(proc.stderr or proc.stdout).strip()}")
        return proc.stdout

    def _ensure_git_repo(self):
        if os.path.exists(os.path.join(self.repo_path, ".git")):
            return
        self._git("init", "-b", MAIN_BRANCH)
        self._git("config", "user.name", os.getenv("GIT_USER_NAME", "Darwin Bot"))
        self._git("config", "user.email", os.getenv("GIT_USER_EMAIL", "bot@darwin.ai"))
        logger.info(f"🌱 Repositório git inicializado em: {self.repo_path}")

    def has_commits(self) -> bool:
        return self._git("rev-parse", "--verify", "HEAD", check=False).strip() != ""

    def seed_from_source(self) -> bool:
        """Copia o código da aplicação para o repo e cria o commit inicial (idempotente)."""
        if self.has_commits():
            return False
        if not self.source_path or not os.path.isdir(self.source_path):
            logger.warning("⚠️ Repositório vazio e APP_SOURCE_PATH indisponível; nada para semear.")
            return False

        shutil.copytree(self.source_path, self.repo_path, ignore=_SEED_IGNORE, dirs_exist_ok=True)
        self._git("add", "-A")
        self._git("commit", "-m", "chore: seed repository from application source")
        logger.info(f"🌱 Repositório semeado a partir de {self.source_path}")
        return True

    def head(self, ref: str = "HEAD") -> str:
        return self._git("rev-parse", ref).strip()

    def _checkout_main(self):
        self._git("checkout", "-f", MAIN_BRANCH)
        self._git("clean", "-fdq")

    # ── patches candidatos ────────────────────────────────────────────────────
    def create_candidate_branch(self, changes: dict, rule: str = "patch", cycle_id: str = "") -> dict:
        """
        Cria um branch `darwin/<rule>_<timestamp>_<id>` com `changes` ({relpath: conteúdo}).
        Retorna {"branch", "commit", "diff", "files"}.
        """
        if not self.has_commits():
            raise GitError("Repositório sem commits: nada para evoluir.")

        with self.lock:
            self._checkout_main()
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch = f"darwin/{rule}_{stamp}_{uuid.uuid4().hex[:6]}"
            self._git("checkout", "-b", branch)
            try:
                for rel, content in changes.items():
                    target = os.path.normpath(os.path.join(self.repo_path, rel))
                    if not target.startswith(os.path.normpath(self.repo_path)):
                        raise GitError(f"Caminho fora do repositório: {rel}")
                    write_text(target, content)

                self._git("add", "-A")
                if not self._git("status", "--porcelain").strip():
                    raise NoChanges("A heurística não alterou nenhum arquivo.")

                suffix = f" [cycle {cycle_id}]" if cycle_id else ""
                self._git("commit", "-m", f"darwin({rule}): auto patch{suffix}")
                result = {
                    "branch": branch,
                    "commit": self.head(),
                    "diff": self._git("show", "--patch", "--format=", "HEAD"),
                    "files": sorted(changes.keys()),
                }
            except Exception:
                self._checkout_main()
                self._git("branch", "-D", branch, check=False)
                raise
            self._checkout_main()
            logger.info(f"🪶 Branch candidato criado: {branch}")
            return result

    # ── deploy (promote / rollback) ───────────────────────────────────────────
    def promote(self, branch: str, cycle_id: str = "") -> dict:
        """Integra o branch aprovado em `main` e cria uma tag de deploy."""
        with self.lock:
            self._checkout_main()
            previous = self.head()
            try:
                self._git("merge", "--ff-only", branch)
            except GitError:
                try:
                    self._git("merge", "--no-edit", branch)
                except GitError:
                    self._git("merge", "--abort", check=False)
                    self._checkout_main()
                    raise
            commit = self.head()
            tag = f"darwin/deploy-{(cycle_id or commit)[:8]}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self._git("tag", tag)
            logger.info(f"🚀 {branch} promovido para {MAIN_BRANCH}: {commit[:8]} (tag {tag})")
            return {"commit": commit, "previous_commit": previous, "tag": tag}

    def rollback(self, commit: str, cycle_id: str = "") -> dict:
        """Reverte um commit promovido (merge ou commit simples) em `main`."""
        with self.lock:
            self._checkout_main()
            parents = self._git("rev-list", "--parents", "-n", "1", commit).split()
            args = ["revert", "--no-edit"]
            if len(parents) > 2:  # commit de merge
                args += ["-m", "1"]
            try:
                self._git(*args, commit)
            except GitError:
                self._git("revert", "--abort", check=False)
                self._checkout_main()
                raise
            new_head = self.head()
            tag = f"darwin/rollback-{(cycle_id or commit)[:8]}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self._git("tag", tag)
            logger.info(f"⏪ Rollback de {commit[:8]} concluído: {new_head[:8]} (tag {tag})")
            return {"commit": new_head, "reverted": commit, "tag": tag}
