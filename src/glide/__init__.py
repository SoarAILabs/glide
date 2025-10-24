"""
Glide - A Python package with Rust extensions for high-performance operations.
"""

from .glide import gemini_service, helix_service, embed_service, commit_splitter

__version__ = "0.0.1"
__all__ = ["gemini_service", "helix_service", "embed_service", "commit_splitter"]
