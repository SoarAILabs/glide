## How to Use

### 1. Clone the repository

```bash
git clone https://github.com/SoarAILabs/glide.git
```

### 2. Navigate to the project directory

```bash
cd glide
```

### 3. Start the server

```bash
uv run python -m src.mcp.app
```

> **Note:** Currently, only [Cursor](https://www.cursor.so/) is supported as the MCP Client.

### 4. Configure Cursor to use your local MCP server

**One-Click Install:**

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=glide&config=eyJjb21tYW5kIjoidXYgcnVuIC0tZGlyZWN0b3J5IFBBVEhcXHRvXFx5b3VyXFxnbGlkZVxcZGlyZWN0b3J5IHB5dGhvbiAtbSBzcmMubWNwLmFwcCJ9)

**Manual Installation:**

Add the following to your `mcp.json` configuration in Cursor:

```json
{
  "mcpServers": {
    "glide": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

> **Note:** The port (`8000` above) is just an example.  
> To use a different port, open `src/mcp/app.py` and update the following lines accordingly:

```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
```

Replace `8000` with your desired port number.