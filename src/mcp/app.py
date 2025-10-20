from fastmcp import FastMCP

mcp = FastMCP("glide")


@mcp.tool
async def commit_splitter():
    return "commit splitter ran successfully!"


@mcp.tool
async def draft_pr():
    return "draft pr ran succesfully!"


@mcp.tool
async def resolve_conflict():
    return "resolve conflict ran successfully"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)
