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


async def find_git_root(start_path: str = None) -> str:
    """
    Find the git repository root directory.
    
    Args:
        start_path: Directory to start searching from (defaults to current working directory)
        
    Returns:
        Path to the git repository root, or None if not in a git repository
    """
    # First, try to get workspace root from common environment variables
    # MCP clients like Cursor might set these
    env_vars = [
        "MCP_WORKSPACE_ROOT",
        "CURSOR_WORKSPACE_ROOT", 
        "WORKSPACE_ROOT",
        "WORKSPACE_FOLDER",
        "PROJECT_ROOT"
    ]
    
    for env_var in env_vars:
        workspace_from_env = os.getenv(env_var)
        if workspace_from_env and os.path.isdir(workspace_from_env):
            # Try to find git root starting from this directory
            start_path = workspace_from_env
            break
    
    if start_path is None:
        start_path = os.getcwd()
    
    # Use git rev-parse --show-toplevel to find the git root
    # Use asyncio.create_subprocess_exec directly to avoid circular dependency
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "rev-parse",
            "--show-toplevel",
            cwd=start_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        stdout_data, stderr_data = await process.communicate()
        
        if process.returncode == 0:
            git_root = stdout_data.decode('utf-8').strip()
            if git_root:
                return git_root
    except (FileNotFoundError, OSError):
        # Git not found or other OS error
        pass
    
    return None


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
async def split_commit(workspace_root: str = None):
    """
    Split a large commit into smaller semantic commits.
    
    Args:
        workspace_root: Optional path to the workspace root directory. 
                        If not provided, will attempt to detect from environment variables or current directory.
    """
    try:
        # Detect the git repository root
        if workspace_root:
            # If provided, use it directly
            detected_root = await find_git_root(workspace_root)
            if detected_root:
                workspace_root = detected_root
            elif not os.path.isdir(workspace_root):
                return f"error: provided workspace_root '{workspace_root}' does not exist or is not a directory."
            # If workspace_root is provided but not a git repo, we'll still try to use it
            # (git commands will fail with a clear error if it's not a git repo)
        else:
            # Try to auto-detect
            workspace_root = await find_git_root()
            if not workspace_root:
                cwd = os.getcwd()
                return (
                    f"error: could not detect git repository root.\n"
                    f"Current working directory: {cwd}\n"
                    f"Please either:\n"
                    f"  1. Run this tool from within a git repository, or\n"
                    f"  2. Provide the workspace_root parameter with the path to your git repository root."
                )
        
        # 1) Collect changed files and per-file unified diffs
        # Check staged, unstaged, and untracked files
        staged_proc = await run_subprocess(
            ["git", "diff", "--cached", "--name-only"], 
            capture_output=True, 
            text=True,
            cwd=workspace_root
        )
        unstaged_proc = await run_subprocess(
            ["git", "diff", "--name-only"], 
            capture_output=True, 
            text=True,
            cwd=workspace_root
        )
        untracked_proc = await run_subprocess(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            cwd=workspace_root
        )
        
        # Check if git commands failed (might indicate not a git repo)
        # Note: git commands can return non-zero even in valid repos (e.g., no changes)
        # Only error if we get explicit "not a git repository" messages
        error_messages = []
        if staged_proc.returncode != 0 and staged_proc.stderr:
            error_messages.append(staged_proc.stderr)
        if "not a git repository" in " ".join(error_messages).lower():
            error_msg = f"error: '{workspace_root}' is not a git repository.\n"
            error_msg += f"Git error: {error_messages[0] if error_messages else 'Unknown error'}\n"
            error_msg += "Please provide the correct path to your git repository root."
            return error_msg

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
                ["git", "diff", "--cached", "--", path], 
                capture_output=True, 
                text=True,
                cwd=workspace_root
            )
            if p.returncode == 0 and p.stdout.strip():
                file_to_diff[path] = p.stdout
            else:
                p = await run_subprocess(
                    ["git", "diff", "--", path], 
                    capture_output=True, 
                    text=True,
                    cwd=workspace_root
                )
                if p.returncode == 0 and p.stdout.strip():
                    file_to_diff[path] = p.stdout
                else:
                    # For untracked/new files, read the entire file content as the "diff"
                    # Paths from git are relative to workspace root, so join them
                    file_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
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
            # 2a) Embed with timeout (5 seconds)
            try:
                vec_batch = await asyncio.wait_for(
                    asyncio.to_thread(embed_code, diff_text, file_path=file_path),
                    timeout=5
                )
            except asyncio.TimeoutError:
                return f"error: embedding timed out for {file_path} (expected to always work)"
            except Exception as embed_exc:
                return f"error: embedding failed for {file_path}: {str(embed_exc)} (expected to always work)"
            
            if not vec_batch:
                return f"error: embedding returned empty result for {file_path}"
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
            
            # Helper function to detect and reject generic messages
            def is_generic_message(msg: str) -> bool:
                """Check if a commit message is too generic."""
                if not msg:
                    return True
                msg_lower = msg.lower().strip()
                generic_patterns = [
                    "update ",
                    "fix bug",
                    "fix issue",
                    "refactor code",
                    "changes",
                    "wip",
                    "misc",
                    "cleanup",
                    "minor",
                    "temporary",
                ]
                # Check if message starts with generic patterns
                for pattern in generic_patterns:
                    if msg_lower.startswith(pattern):
                        return True
                # Check if message is just a filename (e.g., "Update app.py")
                if msg_lower.startswith("update ") and len(msg_lower.split()) <= 3:
                    return True
                return False
            
            system_prompt = (
                """You are a senior engineer writing conventional commit messages. Analyze the diff carefully to understand what actually changed.

CRITICAL REQUIREMENTS:
- Write ONLY a single, concise commit title (under 50 characters preferred)
- Use conventional commit format: type(scope): description
- Common types: feat, fix, refactor, docs, style, test, chore, perf, build, ci
- No issue references, no trailing period
- Be SPECIFIC about what changed - analyze the actual code changes in the diff
- Output ONLY the commit message title, nothing else (no explanations, no prefixes, no quotes)

STRICT PROHIBITIONS - NEVER USE THESE PATTERNS:
- "Update [filename]" (e.g., "Update app.py") - ABSOLUTELY FORBIDDEN
- "Fix bug" - TOO GENERIC
- "Refactor code" - TOO GENERIC  
- "Changes" - TOO GENERIC
- "WIP" - TOO GENERIC
- Any message that doesn't describe what actually changed

GUIDELINES:
- Analyze the actual code changes in the diff to determine the type and description
- For new features: use "feat:" - describe what capability was added (e.g., "feat(auth): add JWT token validation")
- For bug fixes: use "fix:" - describe what was broken and fixed (e.g., "fix(api): handle null response in user endpoint")
- For refactoring: use "refactor:" - describe what was improved without changing behavior (e.g., "refactor(utils): extract common validation logic")
- For configuration/build: use "chore:" or "build:" - describe what was configured (e.g., "chore(deps): update dependencies")
- For documentation: use "docs:" - describe what documentation was added/changed (e.g., "docs(api): add endpoint documentation")
- Include the affected component/file in scope if it adds clarity

EXAMPLES OF GOOD MESSAGES:
- "feat(auth): add JWT token validation"
- "fix(api): handle null response in user endpoint"
- "refactor(utils): extract common validation logic"
- "chore(deps): update numpy to 2.0.0"
- "docs(readme): add installation instructions"

EXAMPLES OF BAD MESSAGES (DO NOT USE):
- "Update app.py" ❌
- "Fix bug" ❌
- "Refactor code" ❌
- "Changes" ❌

Remember: Your output must be SPECIFIC and describe WHAT changed, not generic file operations."""
            )
            user_prompt = (
                "Generate a commit message for this diff. Consider similar past changes if given.\n\n"
                f"DIFF (truncated if long):\n{diff_text}\n\n"
                f"SIMILAR EXAMPLES:\n{example_block}\n\n"
                "Output ONLY the commit message title, nothing else."
            )
            
            # Call Cerebras inference - should always work
            try:
                raw_response = await asyncio.wait_for(
                    complete(user_prompt, system=system_prompt, max_tokens=100),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                return f"error: Cerebras inference timed out for {file_path} (expected to always work)"
            except Exception as llm_exc:
                return f"error: Cerebras inference failed for {file_path}: {str(llm_exc)} (expected to always work)"
            
            if not raw_response:
                return f"error: Cerebras inference returned empty response for {file_path}"
            
            commit_message = raw_response.strip().splitlines()[0].strip()
            
            # Remove quotes if present
            if commit_message.startswith('"') and commit_message.endswith('"'):
                commit_message = commit_message[1:-1]
            if commit_message.startswith("'") and commit_message.endswith("'"):
                commit_message = commit_message[1:-1]
            
            # Validate the message is not generic - fail if it is
            if not commit_message or is_generic_message(commit_message):
                return (
                    f"error: Cerebras inference generated generic message '{commit_message}' for {file_path}. "
                    f"Please improve the system prompt or check the inference output."
                )

            suggestions.append((file_path, commit_message))

        if not suggestions:
            return "no commit suggestions could be generated"

        # 4) Commit each file separately with its suggested message
        for file_path, message in suggestions:
            try:
                await run_subprocess(
                    ["git", "add", "--", file_path], 
                    check=True,
                    cwd=workspace_root
                )
                await run_subprocess(
                    ["git", "commit", "-m", message], 
                    check=True,
                    cwd=workspace_root
                )
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
