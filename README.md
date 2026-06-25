# Guarded AI Agent MCP

A modular, MongoDB-backed AI agent system with real-time policy enforcement and admin dashboard control.

## Features

- **Real-time Policy Management**: Create and toggle rules via admin dashboard without restarting the agent
- **MongoDB-backed Storage**: All rules and logs are persisted in MongoDB
- **Live Tool Discovery**: Dynamically discovers available MCP tools
- **Admin Dashboard**: Web-based UI for rule management and log monitoring
- **Conflict Resolution**: Most restrictive rule wins automatically

## Architecture

```
MCP Servers (stdio/http/sse) -> Transport Layer -> Policy Engine (MongoDB) -> Agent -> FastAPI/Dashboard
```

## Prerequisites

- Python 3.8+
- MongoDB Atlas access
- MCP Server implementation, plus optional access to a remote MCP server such as Context7

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Vamshi9415/guarded-ai-agent-mcp.git
cd guarded-ai-agent-mcp
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and update the values:

```bash
# MongoDB Configuration (Atlas)
MONGO_TYPE=atlas
MONGO_USER=vamshibachu23_db_user
MONGO_PASS=replace-with-your-password
MONGO_HOST_URI=clusterwms.v46ontq.mongodb.net
MONGO_DB_NAME=wms_database
MONGO_AUTH_SRC=wms_database
MONGO_REWRITES=true
MONGO_W=majority
MONGO_HEARTBEAT_MS=60000
MONGO_APP_NAME=Clusterwms

# MongoDB Collections
MONGO_COLL_CUSTOM_SEQUENCE=customSequence

# FastAPI Configuration
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

# MCP Server Configuration
MCP_SERVER_ID=local-file-mcp
MCP_SERVER_COMMAND=python
MCP_SERVER_ARGS=mcp-server/server.py

MCP_REMOTE_SERVER_ID=remote-context7
MCP_REMOTE_SERVER_TRANSPORT=http
MCP_REMOTE_SERVER_URL=https://mcp.context7.com/mcp
```

### 4. Verify MongoDB Atlas Access

Make sure your current IP address is allowed in MongoDB Atlas and that the configured database user has access to `wms_database`.

## Running the Application

### Start the FastAPI Server

```bash
python backend/main.py
```

The server will start on `http://localhost:8000`

### Access the Admin Dashboard

Open your browser and navigate to:

```
http://localhost:8000
```

## Using the Dashboard

### Creating Rules

1. Navigate to the **Create Rule** section
2. Fill in the form:
   - **Tool Name**: Name of the MCP tool (e.g., `filesystem_read`)
   - **Action**: `allow` or `deny`
   - **Condition**: Optional JSON condition (e.g., `{"path": "/safe/*"}`)
   - **Priority**: Higher values = higher priority (default: 1)
3. Click **Create Rule**

### Managing Rules

- View all rules in the **Active Rules** table
- Toggle rules on/off with the **Active** switch
- Changes take effect immediately (no restart needed!)

### Monitoring Logs

- View recent agent activity in the **Recent Logs** section
- See tool calls, policy decisions, and outcomes
- Logs update in real-time

## Project Structure

```
guarded-ai-agent-mcp/
|-- backend/
|   |-- db.py              # MongoDB connection
|   |-- policy.py          # Policy engine logic
|   `-- main.py            # FastAPI entry point
|-- dashboard/
|   `-- index.html         # Admin UI
|-- .env.example           # Environment template
|-- requirements.txt       # Python dependencies
`-- README.md              # This file
```

## How It Works

1. **Agent Startup**: Connects to each configured MCP server and discovers available tools
2. **Policy Polling**: Checks MongoDB every 2 seconds for policy updates
3. **Rule Enforcement**: Before executing any tool, checks active rules
4. **Conflict Resolution**: If multiple rules match, the most restrictive wins
5. **Logging**: All decisions and actions are logged to MongoDB

## API Endpoints

- `GET /` - Admin dashboard
- `GET /rules` - List all rules
- `POST /rules` - Create a new rule
- `PUT /rules/{rule_id}/toggle` - Toggle rule active status
- `GET /logs` - Get recent logs

## Development

### Running in Development Mode

```bash
uvicorn backend.main:app --reload
```


### Running Tests

The default test suite is offline and does not call Gemini, MongoDB Atlas, or live MCP servers. It uses fakes for the LLM, Mongo collections, and MCP sessions so policy and agent behavior can be checked quickly and repeatably.

```bash
python -m pytest -p no:cacheprovider
```

Current coverage includes:

- Policy decisions: allow, block, wildcard block, human approval, input validation, token budget, and conflict priority
- Agent tool-use loop: live MCP tool discovery, allowed execution, blocked execution, approval timeout/approval success, malformed tool names
- FastAPI routes: chat, tools, rules, approvals, logs, and dashboard serving
- MongoDB helper functions: rule create/list/toggle/delete and audit log serialization
- MCP transport manager: malformed tool names, missing sessions, successful routing, and crashed-server errors
- Custom MCP file server: sandbox path safety and read/write/list/search/delete behavior
- Config/import smoke tests: Mongo URI building and backend imports without network startup

The real MongoDB connectivity check is opt-in because it needs credentials, DNS, and Atlas network access:

```bash
RUN_MONGO_INTEGRATION=1 python -m pytest tests/testmongo.py -m integration
```
### Testing Policy Updates

1. Create a rule via dashboard
2. Observe agent logs - rule takes effect within 2 seconds
3. Toggle rule off/on - changes apply immediately

## License

MIT

