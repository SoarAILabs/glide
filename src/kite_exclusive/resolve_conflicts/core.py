import os
import asyncio
from typing import Optional
from dotenv import load_dotenv
import ollama

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.LLM import cerebras_inference


load_dotenv()

# Default model; override per-call via the `model` argument
DEFAULT_MODEL_ID: str = os.getenv("BREEZE_MODEL_ID", "hf.co/SoarAILabs/breeze-3b:Q4_K_M")


def _resolve_merge_conflict_sync(
    conflict_text: str,
    *,
    model: Optional[str] = None,
) -> str:
    # Different test change
    """
    Resolve a merge conflict using the breeze model with Cerebras fallback.
    
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
    except Exception as ollama_error:
        print(f"Ollama failed ({str(ollama_error)}), falling back to Cerebras...")
        
        try:
            system_prompt = (
                "You are a merge conflict resolution assistant. "
                "Analyze the merge conflict and return ONLY the resolved code without conflict markers. "
                "Choose the best implementation from HEAD, base, or branch versions, or merge them intelligently."
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                resolved_content = loop.run_until_complete(
                    cerebras_inference.complete(
                        prompt=conflict_text,
                        system=system_prompt,
                        temperature=0.1, 
                    )
                )
                return resolved_content.strip()
            finally:
                loop.close()
        except Exception as cerebras_error:
            raise RuntimeError(
                f"Both Ollama and Cerebras failed. "
                f"Ollama error: {str(ollama_error)}. "
                f"Cerebras error: {str(cerebras_error)}"
            )


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