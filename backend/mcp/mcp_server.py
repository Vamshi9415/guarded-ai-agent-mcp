import os
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("ArmorIQ-Custom-CRUD-Server")

# In-memory dictionary acting as our isolated database
# It comes pre-seeded with some data for easy demonstration
DB_STORE: Dict[str, Dict[str, Any]] = {
    "user_1": {"name": "Alice", "role": "Admin", "sandbox_path": "/sandbox/data/alice"},
    "user_2": {"name": "Bob", "role": "Developer", "sandbox_path": "/sandbox/data/bob"}
}

@mcp.tool()
def list_records() -> str:
    """List all available records in the database."""
    if not DB_STORE:
        return "Database is currently empty."
    
    result = "Current Records:\n"
    for key, val in DB_STORE.items():
        result += f"- {key}: {val}\n"
    return result

@mcp.tool()
def read_record(key: str) -> str:
    """
    Retrieve a specific record by its key.
    
    Args:
        key: The unique identifier for the record.
    """
    if key in DB_STORE:
        return f"Record found for '{key}': {DB_STORE[key]}"
    return f"Error: Record with key '{key}' not found."

@mcp.tool()
def create_record(key: str, name: str, role: str, storage_path: str = "/sandbox/data") -> str:
    """
    Create a new record in the database.
    
    Args:
        key: Unique identifier for the new record.
        name: Name of the individual.
        role: Job role or permissions level.
        storage_path: The directory path where data must reside (Defaults to /sandbox/data).
    """
    if key in DB_STORE:
        return f"Error: Record with key '{key}' already exists. Use update_record instead."
    
    DB_STORE[key] = {
        "name": name,
        "role": role,
        "storage_path": storage_path
    }
    return f"Success: Created record '{key}' successfully."

@mcp.tool()
def update_record(key: str, name: Optional[str] = None, role: Optional[str] = None, storage_path: Optional[str] = None) -> str:
    """
    Modify an existing record. Partial updates are allowed.
    
    Args:
        key: The unique identifier of the record to update.
        name: Updated name (optional).
        role: Updated role (optional).
        storage_path: Updated directory path (optional).
    """
    if key not in DB_STORE:
        return f"Error: Record with key '{key}' does not exist."
    
    if name is not None:
        DB_STORE[key]["name"] = name
    if role is not None:
        DB_STORE[key]["role"] = role
    if storage_path is not None:
        DB_STORE[key]["storage_path"] = storage_path
        
    return f"Success: Updated record '{key}' successfully. New state: {DB_STORE[key]}"

@mcp.tool()
def delete_record(key: str) -> str:
    """
    Permanently delete a record from the database. Critical operation.
    
    Args:
        key: The unique identifier of the record to delete.
    """
    if key in DB_STORE:
        del DB_STORE[key]
        return f"Success: Record '{key}' has been permanently deleted."
    return f"Error: Record with key '{key}' not found."

if __name__ == "__main__":
    # FastMCP automatically manages the JSON-RPC over stdio communication layer
    mcp.run()