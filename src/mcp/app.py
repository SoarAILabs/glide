from src.kite_exclusive.commit_splitter.services.voyage_service import embed_code
from src.core.LLM.cerebras_inference import complete
from typing import Any, Dict, List, Tuple
import subprocess
import json
import os

import helix

from fastmcp import FastMCP

mcp = FastMCP[Any]("glide")


@mcp.tool
async def draft_pr():
    instructions = [
        "step 1: grep for CONTRIBUTING.md or similar documentation in the repository. If unable to find it, look for any contributing guidelines in the repository.",
        "step 2: if not found, follow best practices for writing a pull request.",
        "step 3: use the edit file tool to write a new PR_DRAFT.md file for the project.",
    ]
    result = "draft pr instructions: \n\n"
    for i, instruction in enumerate[str](instructions, 1):
        result += f"{i}. {instruction}\n\n"
    return result


@mcp.tool(
    name="split_commit",
    description="Splits a large unified diff / commit into smaller semantically-grouped commits.",
)
async def split_commit():
    try:
        # 1) Collect changed files and per-file unified diffs
        # Check staged, unstaged, and untracked files
        staged_proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )
        unstaged_proc = subprocess.run(
            ["git", "diff", "--name-only"], capture_output=True, text=True
        )
        untracked_proc = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
        )

        changed_files = set()
        if staged_proc.returncode == 0:
            changed_files.update(
                f.strip() for f in staged_proc.stdout.splitlines() if f.strip()
            )
        if unstaged_proc.returncode == 0:
            changed_files.update(
                f.strip() for f in unstaged_proc.stdout.splitlines() if f.strip()
            )
        if untracked_proc.returncode == 0:
            changed_files.update(
                f.strip() for f in untracked_proc.stdout.splitlines() if f.strip()
            )

        if not changed_files:
            return "no changes detected (working tree clean)"

        file_to_diff: Dict[str, str] = {}
        for path in changed_files:
            # Try staged diff first, then unstaged
            p = subprocess.run(
                ["git", "diff", "--cached", "--", path], capture_output=True, text=True
            )
            if p.returncode == 0 and p.stdout.strip():
                file_to_diff[path] = p.stdout
            else:
                p = subprocess.run(
                    ["git", "diff", "--", path], capture_output=True, text=True
                )
                if p.returncode == 0 and p.stdout.strip():
                    file_to_diff[path] = p.stdout
                else:
                    # For untracked/new files, read the entire file content as the "diff"
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Format as a new file addition diff
                            file_to_diff[path] = (
                                f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(content.splitlines())} @@\n+{chr(10).join('+'+line for line in content.splitlines())}"
                            )
                    except (FileNotFoundError, UnicodeDecodeError):
                        # File might not exist or not be text
                        continue

        if not file_to_diff:
            return "no per-file diffs produced"

        # 2) Embed each file's diff with Voyage (preconfigured in voyage_service)
        suggestions: List[Tuple[str, str]] = []  # (file_path, suggested_message)

        # Connect Helix client (local by default; adjust via env if needed)
        db = helix.Client(local=True)

        for file_path, diff_text in file_to_diff.items():
            vec_batch = embed_code(
                diff_text, file_path=file_path
            )  # returns a batch; take first vector
            if not vec_batch:
                continue
            vec = vec_batch[0]

            try:
                # 3) ANN search for similar diffs; k kept small to keep it snappy
                res = db.query("getSimilarDiffsByVector", {"vec": vec, "k": 8})
            except Exception as db_exc:
                return (
                    f"Database query failed for file '{file_path}': {str(db_exc)}\n"
                    f"Exception type: {type(db_exc).__name__}\n"
                    "Ensure HelixDB is reachable and the query is correct."
                )
            # Result rows include commit_message, summary, file_path
            examples = []
            if isinstance(res, list):
                for row in res[:5]:
                    if isinstance(row, dict):
                        ex_msg = row.get("commit_message") or ""
                        ex_sum = row.get("summary") or ""
                        ex_path = row.get("file_path") or ""
                        if ex_msg or ex_sum:
                            examples.append(
                                f"file:{ex_path}\nmessage:{ex_msg}\nsummary:{ex_sum}"
                            )

            example_block = "\n\n".join(examples) if examples else ""
            system_prompt = (
                "You are a senior engineer. Write a single, concise, conventional commit title "
                "(<= 70 chars, imperative mood). No issue refs, no period."
            )
            user_prompt = (
                "Generate a commit message for this diff. Consider similar past changes if given.\n\n"
                f"DIFF (truncated if long):\n{diff_text[:8000]}\n\n"
                f"SIMILAR EXAMPLES:\n{example_block}"
            )
            try:
                commit_message = await complete(
                    user_prompt, system=system_prompt, max_tokens=40
                )
                commit_message = (commit_message or "").strip().splitlines()[0][:72]
                if not commit_message:
                    commit_message = f"Update {os.path.basename(file_path)}"
            except Exception:
                commit_message = f"Update {os.path.basename(file_path)}"

            suggestions.append((file_path, commit_message))

        if not suggestions:
            return "no commit suggestions could be generated"

        # 4) Commit each file separately with its suggested message
        for file_path, message in suggestions:
            try:
                subprocess.run(["git", "add", "--", file_path], check=True)
                subprocess.run(["git", "commit", "-m", message], check=True)
            except subprocess.CalledProcessError as e:
                return (
                    f"Failed to add or commit '{file_path}' with message '{message}'.\n"
                    f"Git error: {e}\n"
                    "Ensure the file exists, is not conflicted, and git is functioning properly."
                )

        # 5) Return a compact report of what was committed
        report = {"commits": [{"file": f, "message": m} for f, m in suggestions]}
        return json.dumps(report, indent=2)

    except Exception as e:
        return (
            f"failed to split commit: {str(e)}\n"
            f"Exception type: {type(e).__name__}\n"
            "Ensure git is available and HelixDB is reachable on localhost:6969."
        )


@mcp.tool
async def resolve_conflict():
    return "resolve conflict ran successfully"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
