from helix.embedding.voyageai_client import VoyageAIEmbedder
from helix import Chunk
import os

# Lazy-loaded embedder - only created when needed
_voyage_embedder = None


def _get_embedder():
    """Get or create the voyage embedder instance (lazy initialization)."""
    global _voyage_embedder
    if _voyage_embedder is None:
        _voyage_embedder = VoyageAIEmbedder()
    return _voyage_embedder


def embed_code(code: str, file_path: str = None):

    # For diffs, use token_chunk instead of code_chunk since diffs are text format
    # and code_chunk has API compatibility issues
    try:
        # Try code_chunk first if we have a valid language
        if file_path:
            ext = os.path.splitext(file_path)[1].lstrip(".")
            lang_map = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "jsx": "javascript",
                "tsx": "typescript",
                "java": "java",
                "cpp": "cpp",
                "c": "c",
                "cs": "csharp",
                "go": "go",
                "rs": "rust",
                "rb": "ruby",
                "php": "php",
                "swift": "swift",
                "kt": "kotlin",
                "scala": "scala",
                "sh": "bash",
                "hx": "python",
            }
            language = lang_map.get(ext.lower())
            if language:
                code_chunks = Chunk.code_chunk(code, language=language)
            else:
                code_chunks = Chunk.token_chunk(code)
        else:
            code_chunks = Chunk.token_chunk(code)
    except Exception:
        # Fallback to token_chunk if code_chunk fails
        code_chunks = Chunk.token_chunk(code)

    voyage_embedder = _get_embedder()
    code_embeddings = voyage_embedder.embed_batch([f"{code_chunks}"])

    return code_embeddings
