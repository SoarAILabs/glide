"""
Extract version control information from a Git repo and prepare it
for indexing into the Helix DB schema defined in ``db/schema.hx``.

This module is intentionally side-effect free; call ``index_repository``
from MCP or a CLI entrypoint.
"""

from pathlib import Path
from typing import Dict, Generator, Iterable, Optional

import pygit2


def get_repo_id(repo: pygit2.Repository) -> str:
    """
    Derive a stable repo_id for Helix from the Git config.

    Prefers the 'origin' remote URL if present, otherwise falls back to
    the repository's working directory path.
    """
    try:
        origin = repo.remotes.get("origin")
        if origin is not None and origin.url:
            return origin.url
    except Exception:
        pass

    return str(Path(repo.workdir or Path.cwd()).resolve())


def get_branches(repo: pygit2.Repository) -> Iterable[pygit2.Reference]:
    """
    Return all local branches in the repository as Reference objects.
    """
    return [repo.branches[name] for name in repo.branches.local]


def iter_commits(repo: pygit2.Repository, branch_ref: pygit2.Reference) -> Generator[pygit2.Commit, None, None]:
    """
    Yield all commits reachable from a branch tip (most recent first).
    """
    head_oid = branch_ref.target
    walker = repo.walk(head_oid, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME)
    for commit in walker:
        yield commit


def get_commit_properties(commit: pygit2.Commit) -> Dict[str, object]:
    """
    Map a pygit2.Commit into the properties expected by the Helix Commit node.
    """
    author = commit.author
    author_str = f"{author.name} <{author.email}>" if author and author.email else author.name

    return {
        "commit_id": str(commit.id),
        "short_id": str(commit.id)[:12],
        "author": author_str,
        "message": commit.message or "",
        "committed_at": commit.commit_time,  # epoch seconds; convert to Date on ingest if needed
        "is_merge": len(commit.parents) > 1,
    }


def iter_file_diffs(
    repo: pygit2.Repository,
    commit: pygit2.Commit,
) -> Generator[Dict[str, object], None, None]:
    """
    Yield per-file diff information for a commit, suitable for the Helix Diff + File nodes.

    For non-root commits, we diff against the first parent. For root commits,
    we diff the commit's tree against the empty tree using tree.diff_to_tree()
    as documented in the pygit2 diff guide:
    https://www.pygit2.org/diff.html
    """
    if commit.parents:
        parent = commit.parents[0]
        diff = repo.diff(parent, commit)
    else:
        # Diff empty tree -> commit tree for the initial commit
        tree = commit.tree
        diff = tree.diff_to_tree(swap=True)

    # Mark renames/copies/etc. in-place so status/paths are accurate
    diff.find_similar()

    for patch in diff:
        delta = patch.delta

        old_path = delta.old_file.path
        new_path = delta.new_file.path
        status_char = delta.status_char()  # 'A', 'M', 'D', 'R', etc.

        # Patch.line_stats -> (context, additions, deletions) per pygit2 docs
        _, additions, deletions = patch.line_stats

        try:
            patch_text: Optional[str] = patch.text
        except UnicodeDecodeError:
            # For non-UTF-8 content, fall back to a placeholder
            patch_text = None

        yield {
            "old_path": old_path,
            "new_path": new_path,
            "status": status_char,
            "additions": int(additions),
            "deletions": int(deletions),
            "patch": patch_text or "",
        }


def index_repository(repo_path: Path) -> None:
    """
    Walk the repository and print the data that would be sent to Helix.

    This does NOT perform any Helix writes yet; it just demonstrates the
    data shape for Repository / Branch / Commit / File / Diff nodes.
    """
    repo = pygit2.Repository(str(repo_path))
    repo_id = get_repo_id(repo)

    print(f"Repository repo_id={repo_id!r}")

    for branch_ref in get_branches(repo):
        branch_name = branch_ref.shorthand
        branch_id = f"{repo_id}:{branch_name}"
        print(f"\nBranch branch_id={branch_id!r} name={branch_name!r}")

        for commit in iter_commits(repo, branch_ref):
            commit_props = get_commit_properties(commit)
            print(f"  Commit {commit_props['short_id']} by {commit_props['author']}")

            for diff_info in iter_file_diffs(repo, commit):
                file_path = diff_info["new_path"] or diff_info["old_path"]
                file_id = f"{repo_id}:{file_path}"

                print(
                    f"    Diff {diff_info['status']} file_id={file_id} "
                    f"+{diff_info['additions']} -{diff_info['deletions']} path={file_path}"
                )


if __name__ == "__main__":
    index_repository(Path.cwd())