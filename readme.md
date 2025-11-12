# Glide 

Glide is an MCP server that helps you write better commit messages and resolve merge conflicts with AI assistance. It integrates seamlessly with your development workflow to provide intelligent suggestions based on your code changes.

## Features

- **Smart Commit Messages**: Generate contextual commit messages by analyzing your staged changes
- **Merge Conflict Resolution**: AI-powered assistance for resolving git merge conflicts
- **Vector Search**: Uses embeddings to find similar past commits for better context
- **Multi-language Support**: Works with Python, JavaScript, TypeScript, Java, C++, and more

## Prerequisites

- **Python 3.13+** and `uv` package manager
- **Git** installed and configured
- **Ollama** installed locally (required for merge conflict resolution)
  - Install: https://ollama.ai
  - Pull the model: `ollama pull hf.co/SoarAILabs/breeze-3b:Q4_K_M`

## Quick Start


add to cursor :

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=glide-mcp&config=eyJlbnYiOnsiVk9ZQUdFQUlfQVBJX0tFWSI6IiIsIkhFTElYX0FQSV9FTkRQT0lOVCI6IiIsIkNFUkVCUkFTX0FQSV9LRVkiOiIiLCJDRVJFQlJBU19NT0RFTF9JRCI6InF3ZW4tMy0zMmIiLCJIRUxJWF9MT0NBTCI6IkZhbHNlIiwiTU9SUEhMTE1fQVBJX0tFWSI6IiJ9LCJjb21tYW5kIjoidXZ4IC0tZnJvbSBnaXQraHR0cHM6Ly9naXRodWIuY29tL1NvYXJBSUxhYnMvZ2xpZGUuZ2l0IGdsaWRlIn0%3D)


add to claude code: 

```zsh 
claude mcp add --transport stdio glide-mcp --env VOYAGEAI_API_KEY= --env HELIX_API_ENDPOINT= --env CEREBRAS_API_KEY= --env CEREBRAS_MODEL_ID=qwen-3-32b --env HELIX_LOCAL= --env MORPHLLM_API_KEY= -- uvx --from  "git+https://github.com/SoarAILabs/glide.git" "glide"
```

add to vscode:

you can paste this in your mcp.json config in vs code.  

```zsh
    "glide-mcp": {
          "env": {
            "VOYAGEAI_API_KEY": "",
            "HELIX_API_ENDPOINT": "",
            "CEREBRAS_API_KEY": "",
            "CEREBRAS_MODEL_ID": "qwen-3-32b",
            "HELIX_LOCAL": "False",
            "MORPHLLM_API_KEY": ""
        },
        "command": "uvx",
        "args": ["--from", "git+https://github.com/SoarAILabs/glide.git", "glide"]
    }
```


## Notes

- **Merge Conflict Resolution**: Requires Ollama running locally with the models pulled (see Prerequisites). This feature will use cloud inference providers in the future.
- **API Keys**: Some features require API keys (VoyageAI, Cerebras, MorphLLM)
- **Helix API Endpoint**: Contact us for access at `bilwarad@mail.uc.edu` or Discord:
  - Amaan: `amaanwastaken`
  - Ani: `aniruddg`
  - Vish: `vishesh.1301`