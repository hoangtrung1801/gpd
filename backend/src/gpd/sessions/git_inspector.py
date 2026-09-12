import os
from pathlib import Path
import subprocess
from typing import Sequence

from gpd.sessions.schemas import ChangedFile, CommitSummary, GitSnapshot


class GitInspectionError(Exception):
    pass


class GitInspector:
    def __init__(self, allowed_roots: Sequence[Path] | None = None, timeout: float = 5.0):
        self.allowed_roots = [r.resolve() for r in allowed_roots] if allowed_roots else None
        self.timeout = timeout

    def _validate_root(self, repository_root: Path) -> Path:
        resolved = repository_root.resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise GitInspectionError(f"Repository root does not exist or is not a directory: {resolved}")
        if self.allowed_roots is not None:
            if not any(resolved == allowed or allowed in resolved.parents for allowed in self.allowed_roots):
                raise GitInspectionError(f"Repository root is not in allowlist: {resolved}")
        return resolved

    def _run(self, repository_root: Path, args: list[str]) -> str:
        cmd = ["git"] + args
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            res = subprocess.run(
                cmd,
                cwd=repository_root,
                capture_output=True,
                text=False,
                shell=False,
                timeout=self.timeout,
                env=env,
            )
            if res.returncode != 0:
                # Some commands like branch --show-current return 0 even in detached head
                # config --get returns 1 if key not found, which is fine
                if args[0] == "config":
                    return ""
                return res.stdout.decode("utf-8", errors="replace")
            return res.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            raise GitInspectionError(f"Git command timed out after {self.timeout}s: {' '.join(cmd)}") from e
        except Exception as e:
            raise GitInspectionError(f"Git command failed: {e}") from e

    def inspect(self, repository_root: Path) -> GitSnapshot:
        valid_root = self._validate_root(repository_root)
        
        # 1. Top level root
        root_str = self._run(valid_root, ["rev-parse", "--show-toplevel"]).strip()
        actual_root = Path(root_str) if root_str else valid_root

        # 2. Current branch
        branch = self._run(valid_root, ["branch", "--show-current"]).strip()

        # 3. Status porcelain=v1 -z
        raw_status = self._run(valid_root, ["status", "--porcelain=v1", "-z"])
        changed_files = self._parse_status_z(raw_status)

        # 4. Recent commits
        raw_log = self._run(valid_root, ["log", "-5", "--format=%H%x00%s%x00%aI%x00"])
        recent_commits = self._parse_commits_z(raw_log)

        # 5. Remote URL
        remote_url = self._run(valid_root, ["config", "--get", "remote.origin.url"]).strip() or None

        return GitSnapshot(
            root=actual_root,
            branch=branch,
            changed_files=changed_files,
            recent_commits=recent_commits,
            remote_url=remote_url,
        )

    def _parse_status_z(self, raw: str) -> list[ChangedFile]:
        if not raw:
            return []
        items = raw.split("\0")
        files: list[ChangedFile] = []
        i = 0
        while i < len(items):
            entry = items[i]
            if not entry:
                i += 1
                continue
            status_code = entry[:2]
            path = entry[3:].strip()
            
            # Determine kind
            kind = "modified"
            if "??" in status_code:
                kind = "untracked"
            elif "A" in status_code:
                kind = "added"
            elif "D" in status_code:
                kind = "deleted"
            elif "R" in status_code:
                kind = "renamed"
                # Consumes next token for rename old path
                if i + 1 < len(items):
                    i += 1
            elif "M" in status_code:
                kind = "modified"

            if path:
                files.append(ChangedFile(path=path, change_kind=kind))
            i += 1
        return files

    def _parse_commits_z(self, raw: str) -> list[CommitSummary]:
        if not raw:
            return []
        tokens = raw.split("\0")
        commits: list[CommitSummary] = []
        # format was %H%x00%s%x00%aI%x00 -> tokens are hash, subject, authored_at, (newline)
        i = 0
        while i + 2 < len(tokens):
            c_hash = tokens[i].strip()
            if not c_hash:
                i += 1
                continue
            message = tokens[i + 1]
            authored_at = tokens[i + 2]
            commits.append(CommitSummary(hash=c_hash, message=message, authored_at=authored_at))
            i += 3
        return commits
