from pathlib import Path
import subprocess
import pytest

from gpd.sessions.git_inspector import ChangedFile, GitInspector, GitSnapshot


def test_git_inspector_returns_repository_relative_changes(git_repo: Path):
    payment_file = git_repo / "src" / "payment" / "service.ts"
    payment_file.parent.mkdir(parents=True, exist_ok=True)
    payment_file.write_text("export const pay = () => true;\n")
    
    # Commit first so modifying it later registers as modified
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "Add payment service"], cwd=git_repo, check=True)
    
    # Modify it
    payment_file.write_text("export const pay = () => false;\n")
    
    # Also add an untracked file
    untracked = git_repo / "src" / "untracked.ts"
    untracked.write_text("export const x = 1;\n")
    
    inspector = GitInspector()
    snapshot = inspector.inspect(git_repo)
    
    assert snapshot.branch == "feature/payment"
    paths = {f.path: f.change_kind for f in snapshot.changed_files}
    assert "src/payment/service.ts" in paths
    assert paths["src/payment/service.ts"] == "modified"
    assert "src/untracked.ts" in paths
    assert paths["src/untracked.ts"] in ("untracked", "added")
    assert len(snapshot.recent_commits) >= 1
    assert snapshot.recent_commits[0].message == "Add payment service"


def test_git_inspector_handles_clean_repo(git_repo: Path):
    inspector = GitInspector()
    snapshot = inspector.inspect(git_repo)
    assert snapshot.branch == "feature/payment"
    assert snapshot.changed_files == []


def test_git_inspector_handles_deleted_and_renamed_files(git_repo: Path):
    f1 = git_repo / "file1.txt"
    f1.write_text("hello")
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add file1"], cwd=git_repo, check=True)
    
    # Delete f1
    f1.unlink()
    inspector = GitInspector()
    snapshot = inspector.inspect(git_repo)
    deleted = [f for f in snapshot.changed_files if f.path == "file1.txt"]
    assert len(deleted) == 1
    assert deleted[0].change_kind == "deleted"


def test_git_inspector_handles_detached_head(git_repo: Path):
    subprocess.run(["git", "checkout", "--detach"], cwd=git_repo, check=True)
    inspector = GitInspector()
    snapshot = inspector.inspect(git_repo)
    assert snapshot.branch == "" or "HEAD" in snapshot.branch or "detached" in snapshot.branch
