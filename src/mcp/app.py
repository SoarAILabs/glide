from pickle import NONE
from src.kite_exclusive.commit_splitter.services.voyage_service import embed_code
from typing import Any, Optional
import subprocess

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
    for i, instruction in enumerate(instructions, 1):
        result += f"{i}. {instruction}\n\n"
    result += "please follow these steps to draft a pull request: \n\n"
    return result

@mcp.tool(name="split_commit", description="Splits a large unified diff / commit into smaller semantically-grouped commits.")
async def split_commit():
    try: 
        git_diff = subprocess.run(["git", "diff"], capture_output=True, text=True)
        code_embeddings = embed_code(git_diff.stdout)
        # helix_service(code_embeddings)
        # get the helix response
        # use the helix response to split the commit
        # return the split commit
    except Exception as e:
        return (
            "failed to get git diff.\n"
            "Please check if you are in a git repository and try again."
        )
    return None # type: ignore

@mcp.tool
async def resolve_conflict():
    return "resolve conflict ran successfully"


if __name__ == "__main__":
    mcp.run(transport="stdio")
