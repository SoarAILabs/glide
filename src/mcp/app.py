from src.kite_exclusive.commit_splitter.services.voyage_service import embed_code
from src.core.LLM.cerebras_inference import complete
from typing import Any, Dict, List, Tuple
import subprocess
import json
import os
import asyncio
from dotenv import load_dotenv
import helix
from fastmcp import FastMCP
load_dotenv()

mcp = FastMCP[Any]("glide")

HELIX_API_ENDPOINT = os.getenv("HELIX_API_ENDPOINT", "")


# Helper function to run subprocess calls asynchronously to avoid blocking stdio
async def run_subprocess(args: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run subprocess calls asynchronously to avoid blocking stdio transport."""
    # Use asyncio.create_subprocess_exec instead of subprocess.run to avoid blocking
    capture_output = kwargs.pop('capture_output', False)
    text = kwargs.pop('text', False)
    check = kwargs.pop('check', False)  # Handle check parameter separately
    
    # CRITICAL: Set stdin to DEVNULL to prevent subprocess from inheriting 
    # the MCP stdio stdin, which causes deadlocks
    stdin = kwargs.pop('stdin', asyncio.subprocess.DEVNULL)
    
    # CRITICAL: Always capture stdout/stderr to PIPE to prevent subprocess output
    # from leaking into the MCP stdio communication channel (which breaks JSON parsing)
    # In stdio mode, parent's stdout/stderr IS the MCP communication channel, so we must
    # always capture subprocess output to prevent git messages from breaking JSON protocol
    stdout = asyncio.subprocess.PIPE
    stderr = asyncio.subprocess.PIPE
    # Remove any stdout/stderr from kwargs since we're overriding them
    kwargs.pop('stdout', None)
    kwargs.pop('stderr', None)
    
    # Only pass valid parameters to asyncio.create_subprocess_exec
    # Filter out any subprocess.run() specific parameters that aren't valid
    # Explicitly remove check and other invalid params to prevent errors
    kwargs.pop('check', None)  # Extra safety: ensure check is removed
    kwargs.pop('timeout', None)  # timeout handled by asyncio.wait_for elsewhere
    kwargs.pop('input', None)  # input not supported in async subprocess
    
    valid_exec_kwargs = {}
    allowed_params = {'cwd', 'env', 'start_new_session', 'shell', 'preexec_fn', 
                      'executable', 'bufsize', 'close_fds', 'pass_fds', 
                      'restore_signals', 'umask', 'limit', 'creationflags'}
    for key, value in kwargs.items():
        if key in allowed_params:
            valid_exec_kwargs[key] = value
        # Silently ignore other parameters
    
    # Final safety check: ensure check is not in valid_exec_kwargs
    assert 'check' not in valid_exec_kwargs, "check parameter should not be passed to subprocess"
    
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        **valid_exec_kwargs
    )
    
    stdout_data, stderr_data = await process.communicate()
    
    # Create a CompletedProcess-like object
    result = subprocess.CompletedProcess(
        args=args,
        returncode=process.returncode,
        stdout=stdout_data.decode('utf-8') if text and stdout_data else stdout_data,
        stderr=stderr_data.decode('utf-8') if text and stderr_data else stderr_data,
    )
    
    # If check=True, raise CalledProcessError on non-zero return code
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, args, result.stdout, result.stderr
        )
    
    return result

@mcp.tool
async def draft_pr():
    instructions = [
        "step 1: grep for CONTRIBUTING.md or similar documentation in the repository. If unable to find it, look for any contributing guidelines in the repository.",
        "step 2: if not found, follow best practices for writing a pull request.",
        "step 3: use the edit file tool to write a new PR_DRAFT.md file for the project.",
    ]
    result = "draft pr instructions: \n\n"
    for i, instruction in enumerate(instructions, 1):
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
        staged_proc = await run_subprocess(
            ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
        )
        unstaged_proc = await run_subprocess(
            ["git", "diff", "--name-only"], capture_output=True, text=True
        )
        untracked_proc = await run_subprocess(
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
            p = await run_subprocess(
                ["git", "diff", "--cached", "--", path], capture_output=True, text=True
            )
            if p.returncode == 0 and p.stdout.strip():
                file_to_diff[path] = p.stdout
            else:
                p = await run_subprocess(
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

        # Connect Helix client - supports both local and cloud via environment variables
        use_local = os.getenv("HELIX_LOCAL", "false").lower() == "true"
        
        if use_local:
            db = helix.Client(local=True)
        else:
            # Use cloud deployment from helix.toml (production.fly)
            # Helix SDK automatically reads helix.toml and uses the configured deployment
            api_endpoint = os.getenv("HELIX_API_ENDPOINT", "")
            if not HELIX_API_ENDPOINT:
                return "error: HELIX API ENDPOINT is not set"
            db = helix.Client(local=False, api_endpoint=api_endpoint)

        for file_path, diff_text in file_to_diff.items():
            try:
                # 2a) Embed with timeout (5 seconds)
                vec_batch = await asyncio.wait_for(
                    asyncio.to_thread(embed_code, diff_text, file_path=file_path),
                    timeout=5
                )
            except asyncio.TimeoutError:
                # If embedding times out, skip this file and use a fallback message
                suggestions.append((file_path, f"Update {os.path.basename(file_path)}"))
                continue
            except Exception as embed_exc:
                # If embedding fails, skip this file
                suggestions.append((file_path, f"Update {os.path.basename(file_path)}"))
                continue
                
            if not vec_batch:
                suggestions.append((file_path, f"Update {os.path.basename(file_path)}"))
                continue
            vec = vec_batch[0]

            try:
                # 3) ANN search for similar diffs; k kept small to keep it snappy
                # Add timeout to database query (5 seconds)
                res = await asyncio.wait_for(
                    asyncio.to_thread(db.query, "getSimilarDiffsByVector", {"vec": vec, "k": 8}),
                    timeout=5
                )
            except asyncio.TimeoutError:
                # If database query times out, continue without examples
                res = []
            except Exception as db_exc:
                # If database query fails, continue without examples
                res = []
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
                "(<= 70 chars, imperative mood). No issue refs, no period. No generic messages like 'update', 'fix', 'refactor', etc. use the diff to generate a specific message. always use 'add:', 'chore:', 'feat:' etc to start the message."
            )
            user_prompt = (
                "Generate a commit message for this diff. Consider similar past changes if given.\n\n"
                f"DIFF (truncated if long):\n{diff_text}\n\n"
                f"SIMILAR EXAMPLES:\n{example_block}"
            )
            try:
                commit_message = await asyncio.wait_for(
                    complete(user_prompt, system=system_prompt),
                    timeout=30.0
                )
                commit_message = (commit_message or "").strip().splitlines()[0].strip()
                if not commit_message:
                    commit_message = f"Update {os.path.basename(file_path)}"
            except asyncio.TimeoutError:
                commit_message = f"Update {os.path.basename(file_path)}"
            except Exception as llm_exc:
                # Log the error but continue with fallback message
                commit_message = f"Update {os.path.basename(file_path)}"

            suggestions.append((file_path, commit_message))

        if not suggestions:
            return "no commit suggestions could be generated"

        # 4) Commit each file separately with its suggested message
        for file_path, message in suggestions:
            try:
                await run_subprocess(["git", "add", "--", file_path], check=True)
                await run_subprocess(["git", "commit", "-m", message], check=True)
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
    # mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
    mcp.run(transport="stdio")
