from src.kite_exclusive.commit_splitter.services.voyage_service import embed_code
from src.core.LLM.cerebras_inference import complete
from src.kite_exclusive.resolve_conflicts.core import resolve_merge_conflict
from src.kite_exclusive.resolve_conflicts.morph_service import apply_code_edit
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import json
import os
import asyncio
import re
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
            start_path = workspace_from_env
            break
    
    if start_path is None:
        start_path = os.getcwd()
    
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
        pass
    
    return None


async def run_subprocess(args: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run subprocess calls asynchronously to avoid blocking stdio transport."""
    capture_output = kwargs.pop('capture_output', False)
    text = kwargs.pop('text', False)
    check = kwargs.pop('check', False)
    
    stdin = kwargs.pop('stdin', asyncio.subprocess.DEVNULL)
    stdout = asyncio.subprocess.PIPE
    stderr = asyncio.subprocess.PIPE
    kwargs.pop('stdout', None)
    kwargs.pop('stderr', None)
    kwargs.pop('check', None)
    kwargs.pop('timeout', None)
    kwargs.pop('input', None)
    
    valid_exec_kwargs = {}
    allowed_params = {'cwd', 'env', 'start_new_session', 'shell', 'preexec_fn', 
                      'executable', 'bufsize', 'close_fds', 'pass_fds', 
                      'restore_signals', 'umask', 'limit', 'creationflags'}
    for key, value in kwargs.items():
        if key in allowed_params:
            valid_exec_kwargs[key] = value
    
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        **valid_exec_kwargs
    )
    
    stdout_data, stderr_data = await process.communicate()
    
    result = subprocess.CompletedProcess(
        args=args,
        returncode=process.returncode,
        stdout=stdout_data.decode('utf-8') if text and stdout_data else stdout_data,
        stderr=stderr_data.decode('utf-8') if text and stderr_data else stderr_data,
    )
    
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, args, result.stdout, result.stderr
        )
    
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
        if workspace_root:
            detected_root = await find_git_root(workspace_root)
            if detected_root:
                workspace_root = detected_root
            elif not os.path.isdir(workspace_root):
                return f"error: provided workspace_root '{workspace_root}' does not exist or is not a directory."
        else:
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
                    file_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            file_to_diff[path] = (
                                f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(content.splitlines())} @@\n+{chr(10).join('+'+line for line in content.splitlines())}"
                            )
                    except (FileNotFoundError, UnicodeDecodeError):
                        continue

        if not file_to_diff:
            return "no per-file diffs produced"

        suggestions: List[Tuple[str, str]] = []

        use_local = os.getenv("HELIX_LOCAL", "false").lower() == "true"
        
        if use_local:
            db = helix.Client(local=True)
        else:
            api_endpoint = os.getenv("HELIX_API_ENDPOINT", "")
            if not api_endpoint:
                return "error: HELIX_API_ENDPOINT is not set"
            db = helix.Client(local=False, api_endpoint=api_endpoint)

        for file_path, diff_text in file_to_diff.items():
            try:
                vec_batch = await asyncio.wait_for(
                    asyncio.to_thread(embed_code, diff_text, file_path=file_path),
                    timeout=5
                )
            except asyncio.TimeoutError:
                return f"error: embedding timed out for {file_path}"
            except Exception as embed_exc:
                return f"error: embedding failed for {file_path}: {str(embed_exc)}"
            
            if not vec_batch:
                return f"error: embedding returned empty result for {file_path}"
            vec = vec_batch[0]

            try:
                res = await asyncio.wait_for(
                    asyncio.to_thread(db.query, "getSimilarDiffsByVector", {"vec": vec, "k": 8}),
                    timeout=5
                )
            except (asyncio.TimeoutError, Exception):
                res = []
            
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
            
            def is_generic_message(msg: str) -> bool:
                """Check if a commit message is too generic."""
                if not msg:
                    return True
                msg_lower = msg.lower().strip()
                
                # Reject reasoning tag patterns
                if ("redacted_reasoning" in msg_lower or 
                    "<think>" in msg_lower or 
                    "</think>" in msg_lower):
                    return True
                
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
                for pattern in generic_patterns:
                    if msg_lower.startswith(pattern):
                        return True
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
- "Update app.py"
- "Fix bug"
- "Refactor code"
- "Changes"

Remember: Your output must be SPECIFIC and describe WHAT changed, not generic file operations."""
            )
            user_prompt = (
                "/no_think\n\nGenerate a commit message for this diff. Consider similar past changes if given.\n\n"
                f"DIFF (truncated if long):\n{diff_text}\n\n"
                f"SIMILAR EXAMPLES:\n{example_block}\n\n"
                "Output ONLY the commit message title, nothing else."
            )
            
            try:
                raw_response = await asyncio.wait_for(
                    complete(user_prompt, system=system_prompt, temperature=0.0),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                return f"error: Cerebras inference timed out for {file_path}"
            except Exception as llm_exc:
                return f"error: Cerebras inference failed for {file_path}: {str(llm_exc)}"
            
            if not raw_response:
                return f"error: Cerebras inference returned empty response for {file_path}"
            
            # Strip reasoning tags from response (e.g., <think>, </think>, <think>, etc.)
            cleaned_response = raw_response.strip()
            # Remove XML-like reasoning tags
            cleaned_response = re.sub(r'<[^>]*think[^>]*>', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'<[^>]*reasoning[^>]*>', '', cleaned_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'<[^>]*redacted[^>]*>', '', cleaned_response, flags=re.IGNORECASE)
            
            # Extract first non-empty line after cleaning
            lines = [line.strip() for line in cleaned_response.splitlines() if line.strip()]
            if not lines:
                return f"error: No valid commit message found in response for {file_path} after cleaning reasoning tags"
            
            commit_message = lines[0]
            
            if commit_message.startswith('"') and commit_message.endswith('"'):
                commit_message = commit_message[1:-1]
            if commit_message.startswith("'") and commit_message.endswith("'"):
                commit_message = commit_message[1:-1]
            
            if not commit_message or is_generic_message(commit_message):
                return (
                    f"error: Cerebras inference generated generic message '{commit_message}' for {file_path}"
                )

            suggestions.append((file_path, commit_message))

        if not suggestions:
            return "no commit suggestions could be generated"

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

        report = {"commits": [{"file": f, "message": m} for f, m in suggestions]}
        return json.dumps(report, indent=2)

    except Exception as e:
        return f"failed to split commit: {str(e)}"

async def get_conflicted_files(workspace_root: str) -> List[str]:
    """
    Find all files with merge conflicts in the git repository.
    
    Checks both git's merge state and files with conflict markers directly.
    
    Args:
        workspace_root: Path to the git repository root
        
    Returns:
        List of file paths with merge conflicts
    """
    conflicted_files = set()
    
    # Method 1: Check git's merge state (for active merges)
    try:
        proc = await run_subprocess(
            ["git", "ls-files", "-u"],
            capture_output=True,
            text=True,
            cwd=workspace_root
        )
        
        if proc.returncode == 0 and proc.stdout.strip():
            # Extract unique file paths (git ls-files -u shows multiple entries per stage)
            for line in proc.stdout.splitlines():
                if line.strip():
                    # Format: stage_number mode hash filename
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = ' '.join(parts[3:])  # Handle filenames with spaces
                        conflicted_files.add(file_path)
    except Exception:
        pass
    
    # Method 2: Scan files for conflict markers (works even if not in active merge)
    try:
        # Get all tracked files (or modified files)
        proc = await run_subprocess(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=workspace_root
        )
        
        if proc.returncode == 0:
            all_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            
            # Also check untracked/modified files
            proc_modified = await run_subprocess(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                cwd=workspace_root
            )
            if proc_modified.returncode == 0:
                all_files.extend([line.strip() for line in proc_modified.stdout.splitlines() if line.strip()])
            
            # Pattern to match conflict markers
            conflict_pattern = re.compile(r'^<<<<<<<', re.MULTILINE)
            
            for file_path in all_files:
                full_path = os.path.join(workspace_root, file_path) if not os.path.isabs(file_path) else file_path
                
                # Skip if already found via git ls-files -u
                if file_path in conflicted_files:
                    continue
                
                try:
                    # Only check text files (skip binary files)
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # Check for conflict markers
                        if conflict_pattern.search(content):
                            conflicted_files.add(file_path)
                except (FileNotFoundError, UnicodeDecodeError, PermissionError):
                    # Skip files we can't read
                    continue
    except Exception:
        pass
    
    return sorted(list(conflicted_files))

def extract_conflict_content(file_path: str, workspace_root: str) -> Tuple[str, str]:
    """
    Extract conflict content from a file.
    
    Args:
        file_path: Relative path to the conflicted file
        workspace_root: Path to the git repository root
        
    Returns:
        Tuple of (original_file_content, conflict_text_with_markers)
    """
    full_path = os.path.join(workspace_root, file_path) if not os.path.isabs(file_path) else file_path
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            original_content = f.read()
        
        # Extract conflict sections (between <<<<<<< and >>>>>>> markers)
        conflict_pattern = re.compile(
            r'<<<<<<<[^\n]*\n(.*?)\n=======\n(.*?)\n>>>>>>>[^\n]*',
            re.DOTALL
        )
        
        conflicts = conflict_pattern.findall(original_content)
        if not conflicts:
            # If no conflicts found with standard pattern, return the whole file
            # as the conflict (might be a different conflict format)
            return original_content, original_content
        
        # Combine all conflict sections
        conflict_texts = []
        for match in conflict_pattern.finditer(original_content):
            conflict_texts.append(match.group(0))
        
        conflict_text = "\n\n".join(conflict_texts)
        return original_content, conflict_text
    except (FileNotFoundError, UnicodeDecodeError) as e:
        raise RuntimeError(f"Failed to read file {file_path}: {str(e)}")

def format_resolution_as_edit_snippet(original_content: str, conflict_text: str, resolution: str) -> Tuple[str, str]:
    """
    Format the resolution as an edit snippet for morphllm.
    
    Args:
        original_content: Original file content with conflicts
        conflict_text: The conflict section with markers
        resolution: The resolved content from breeze model
        
    Returns:
        Tuple of (instructions, edit_snippet)
    """
    # Find the conflict section in the original content
    conflict_start = original_content.find(conflict_text)
    if conflict_start == -1:
        # If exact match not found, try to find by markers
        conflict_start = original_content.find("<<<<<<<")
    
    if conflict_start == -1:
        # Fallback: replace the entire conflict text
        instructions = "Replace the merge conflict section with the resolved code."
        edit_snippet = resolution
        return instructions, edit_snippet
    
    # Find lines before and after conflict
    lines_before = original_content[:conflict_start].splitlines()
    lines_after = original_content[conflict_start + len(conflict_text):].splitlines()
    
    # Get context lines (last 3 lines before, first 3 lines after)
    context_before = "\n".join(lines_before[-3:]) if lines_before else ""
    context_after = "\n".join(lines_after[:3]) if lines_after else ""
    
    # Determine comment style based on file extension (simple heuristic)
    # Default to // for most languages
    comment_style = "//"
    
    # Build edit snippet
    edit_lines = []
    if context_before:
        edit_lines.append(context_before)
    edit_lines.append(f"{comment_style} ... existing code ...")
    edit_lines.append(resolution)
    edit_lines.append(f"{comment_style} ... existing code ...")
    if context_after:
        edit_lines.append(context_after)
    
    edit_snippet = "\n".join(edit_lines)
    instructions = "Replace the merge conflict markers and conflicting code sections with the resolved code."
    
    return instructions, edit_snippet

@mcp.tool(
    name="resolve_conflict",
    description="Detects merge conflicts in the repository, resolves them using AI, and applies the changes with MorphLLM. Changes are written to files immediately. Use revert_conflict_resolution to undo changes if needed.",
)
async def resolve_conflict(workspace_root: Optional[str] = None):
    """
    Detect and resolve merge conflicts using AI. Changes are applied immediately to files.
    Review the previews and confirm or revert as needed.
    
    Args:
        workspace_root: Optional path to the workspace root directory.
                        If not provided, will attempt to detect from environment variables or current directory.
    
    Returns:
        JSON string with applied resolutions and previews for review
    """
    global _resolved_conflicts
    
    try:
        if workspace_root:
            detected_root = await find_git_root(workspace_root)
            if detected_root:
                workspace_root = detected_root
            elif not os.path.isdir(workspace_root):
                return json.dumps({"error": f"provided workspace_root '{workspace_root}' does not exist or is not a directory."})
        else:
            workspace_root = await find_git_root()
            if not workspace_root:
                cwd = os.getcwd()
                return json.dumps({
                    "error": "could not detect git repository root.",
                    "current_directory": cwd,
                    "message": "Please either run this tool from within a git repository, or provide the workspace_root parameter."
                })
        
        # Find conflicted files
        conflicted_files = await get_conflicted_files(workspace_root)
        
        if not conflicted_files:
            return json.dumps({
                "message": "No merge conflicts detected.",
                "resolved_files": []
            })
        
        resolved_files = []
        _resolved_conflicts = {}  # Store for potential revert
        
        for file_path in conflicted_files:
            try:
                # Extract conflict content
                original_content, conflict_text = extract_conflict_content(file_path, workspace_root)
                
                # Get resolution from breeze model
                try:
                    resolution = await asyncio.wait_for(
                        resolve_merge_conflict(conflict_text),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": "Breeze model timeout"
                    })
                    continue
                except Exception as e:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": f"Breeze model failed: {str(e)}"
                    })
                    continue
                
                if not resolution:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": "Breeze model returned empty resolution"
                    })
                    continue
                
                # Format resolution as edit snippet
                instructions, edit_snippet = format_resolution_as_edit_snippet(
                    original_content, conflict_text, resolution
                )
                
                # Apply via morphllm
                try:
                    final_content = await asyncio.wait_for(
                        apply_code_edit(original_content, instructions, edit_snippet),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": "MorphLLM timeout"
                    })
                    continue
                except Exception as e:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": f"MorphLLM failed: {str(e)}"
                    })
                    continue
                
                # Apply the change immediately by writing to file
                full_path = os.path.join(workspace_root, file_path) if not os.path.isabs(file_path) else file_path
                try:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(final_content)
                except Exception as e:
                    resolved_files.append({
                        "file": file_path,
                        "status": "error",
                        "error": f"Failed to write resolved content: {str(e)}"
                    })
                    continue
                
                # Store original content for potential revert
                _resolved_conflicts[file_path] = {
                    "workspace_root": workspace_root,
                    "original_content": original_content,
                    "resolved_content": final_content,
                }
                
                # Create a simple diff preview (show before/after around conflict)
                conflict_lines = conflict_text.splitlines()
                conflict_preview = "\n".join(conflict_lines[:10])
                if len(conflict_lines) > 10:
                    conflict_preview += f"\n... ({len(conflict_lines) - 10} more lines) ..."
                
                resolved_lines = final_content.splitlines()
                resolved_preview = "\n".join(resolved_lines[:30])
                if len(resolved_lines) > 30:
                    resolved_preview += f"\n... ({len(resolved_lines) - 30} more lines) ..."
                
                resolved_files.append({
                    "file": file_path,
                    "status": "applied",
                    "conflict_preview": conflict_preview,
                    "resolved_preview": resolved_preview,
                    "message": "Changes have been applied to the file. Review and confirm to stage, or revert if needed."
                })
                
            except Exception as e:
                resolved_files.append({
                    "file": file_path,
                    "status": "error",
                    "error": str(e)
                })
        
        successful_count = len([f for f in resolved_files if f.get('status') == 'applied'])
        result = {
            "message": f"Applied resolutions to {successful_count} file(s). Changes have been written to files.",
            "instruction": "Review the resolved files above. You can stage them yourself or use the commit splitter. If you want to undo the changes, call revert_conflict_resolution.",
            "resolved_files": resolved_files
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"failed to resolve conflict: {str(e)}"})


@mcp.tool(
    name="revert_conflict_resolution",
    description="Reverts the resolved conflict files back to their original state with conflicts. Use if you want to undo the changes applied by resolve_conflict.",
)
async def revert_conflict_resolution(file_path: Optional[str] = None, workspace_root: Optional[str] = None, revert_all: bool = False):
    """
    Revert resolved conflict files back to their original conflicted state.
    
    Args:
        file_path: Optional path to a specific file to revert (relative to workspace root).
                   If not provided and revert_all=False, reverts all pending resolutions.
        workspace_root: Optional path to the workspace root directory.
                        If not provided, will attempt to detect from environment variables or current directory.
        revert_all: If True, revert all pending resolutions at once
    
    Returns:
        JSON string with success/error status
    """
    global _resolved_conflicts
    
    try:
        if workspace_root:
            detected_root = await find_git_root(workspace_root)
            if detected_root:
                workspace_root = detected_root
            elif not os.path.isdir(workspace_root):
                return json.dumps({"error": f"provided workspace_root '{workspace_root}' does not exist or is not a directory."})
        else:
            workspace_root = await find_git_root()
            if not workspace_root:
                return json.dumps({"error": "could not detect git repository root."})
        
        if revert_all or not file_path:
            # Revert all pending resolutions
            if not _resolved_conflicts:
                return json.dumps({
                    "message": "No pending resolutions to revert."
                })
            
            reverted_files = []
            errors = []
            
            for path, resolution_data in list(_resolved_conflicts.items()):
                try:
                    # Verify workspace root matches
                    if resolution_data["workspace_root"] != workspace_root:
                        errors.append({"file": path, "error": "Workspace root mismatch"})
                        continue
                    
                    full_path = os.path.join(workspace_root, path) if not os.path.isabs(path) else path
                    
                    # Write original content back to file
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(resolution_data["original_content"])
                    
                    reverted_files.append(path)
                    del _resolved_conflicts[path]
                    
                except Exception as e:
                    errors.append({"file": path, "error": str(e)})
            
            result = {
                "message": f"Reverted {len(reverted_files)} file(s) back to conflicted state.",
                "reverted_files": reverted_files,
                "errors": errors if errors else None
            }
            return json.dumps(result, indent=2)
        else:
            # Revert single file
            if file_path not in _resolved_conflicts:
                return json.dumps({
                    "error": f"No pending resolution found for '{file_path}'."
                })
            
            resolution_data = _resolved_conflicts[file_path]
            
            # Verify workspace root matches
            if resolution_data["workspace_root"] != workspace_root:
                return json.dumps({
                    "error": f"Workspace root mismatch. Expected '{resolution_data['workspace_root']}', got '{workspace_root}'."
                })
            
            full_path = os.path.join(workspace_root, file_path) if not os.path.isabs(file_path) else file_path
            
            # Write original content back to file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(resolution_data["original_content"])
            
            # Remove from pending resolutions
            del _resolved_conflicts[file_path]
            
            return json.dumps({
                "message": f"Reverted '{file_path}' back to conflicted state.",
                "file": file_path
            })
            
    except Exception as e:
        return json.dumps({"error": f"failed to revert conflict resolution: {str(e)}"})


def main():
    """Entry point for the glide-mcp package."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    # mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
    main()
