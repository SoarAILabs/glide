from helix.embedding.voyageai_client import VoyageAIEmbedder
from helix import Chunk

def embed_code(code:str ):         
    voyage_embedder = VoyageAIEmbedder()
    code_chunks = Chunk.code_chunk(code)
    code_embeddings = voyage_embedder.embed_batch([f"{code_chunks}"])

    return code_embeddings