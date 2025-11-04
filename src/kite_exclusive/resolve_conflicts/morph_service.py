import os
import asyncio
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# MorphLLM API configuration
MORPH_API_BASE = "https://api.morphllm.com/v1"
MORPH_MODEL = "morph-v3-fast"

_openai_client: Optional[OpenAI] = None


def _get_api_key() -> str:
    """Get MorphLLM API key from environment."""
    api_key = os.getenv("MORPHLLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MORPHLLM_API_KEY or MORPH_API_KEY is not set. "
            "Set it in the environment or .env file."
        )
    return api_key


def _get_openai_client() -> OpenAI:
    """Get or create the OpenAI client instance for MorphLLM (lazy initialization)."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=_get_api_key(),
            base_url=MORPH_API_BASE,
        )
    return _openai_client


def _apply_code_edit_sync(
    original_code: str,
    instructions: str,
    edit_snippet: str,
) -> str:
    """
    Apply a code edit using MorphLLM.
    
    Args:
        original_code: The original file content
        instructions: Single sentence instruction describing what the edit does
        edit_snippet: The edit snippet with // ... existing code ... markers
        
    Returns:
        Final code with edit applied
    """
    client = _get_openai_client()
    
    # Format the prompt as MorphLLM expects:
    # instructions + original_code + edit_snippet
    prompt = f"{instructions}\n\n{original_code}\n\n{edit_snippet}"
    
    try:
        response = client.chat.completions.create(
            model=MORPH_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        
        if not response or not response.choices or not response.choices[0].message.content:
            raise RuntimeError("MorphLLM returned empty or invalid response")
        
        final_code = response.choices[0].message.content
        return final_code
    except Exception as e:
        raise RuntimeError(f"MorphLLM error: {str(e)}")


async def apply_code_edit(
    original_code: str,
    instructions: str,
    edit_snippet: str,
) -> str:
    """
    Apply a code edit using MorphLLM.
    
    Args:
        original_code: The original file content
        instructions: Single sentence instruction describing what the edit does
        edit_snippet: The edit snippet with // ... existing code ... markers
        
    Returns:
        Final code with edit applied
    """
    return await asyncio.to_thread(
        _apply_code_edit_sync,
        original_code,
        instructions,
        edit_snippet,
    )


__all__ = [
    "apply_code_edit",
]
