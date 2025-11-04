import os
import asyncio
from typing import Optional
from dotenv import load_dotenv
import ollama

load_dotenv()

# Default model; override per-call via the `model` argument
DEFAULT_MODEL_ID: str = os.getenv("BREEZE_MODEL_ID", "hf.co/SoarAILabs/breeze-3b:Q4_K_M")


def _resolve_merge_conflict_sync(
    conflict_text: str,
    *,
    model: Optional[str] = None,
) -> str:
    """
    Resolve a merge conflict using the breeze model.
    
    Args:
        conflict_text: Merge conflict text with markers (<<<<<<<, =======, >>>>>>>)
        model: Model name; defaults to DEFAULT_MODEL_ID
        
    Returns:
        Resolved content without conflict markers
    """
    model_id = model or DEFAULT_MODEL_ID
    
    try:
        response = ollama.generate(
            model=model_id,
            prompt=conflict_text,
        )
        
        if not response or 'response' not in response:
            raise RuntimeError("Ollama returned empty or invalid response")
        
        resolved_content = response['response']
        return resolved_content.strip()
    except Exception as e:
        raise RuntimeError(f"Ollama error: {str(e)}")


async def resolve_merge_conflict(
    conflict_text: str,
    *,
    model: Optional[str] = None,
) -> str:
    """
    Resolve a merge conflict using the breeze model.
    
    Args:
        conflict_text: Merge conflict text with markers (<<<<<<<, =======, >>>>>>>)
        model: Model name; defaults to DEFAULT_MODEL_ID
        
    Returns:
        Resolved content without conflict markers
    """
    return await asyncio.to_thread(
        _resolve_merge_conflict_sync,
        conflict_text,
        model=model,
    )


__all__ = [
    "resolve_merge_conflict",
    "DEFAULT_MODEL_ID",
]
