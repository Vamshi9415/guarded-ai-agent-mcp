# Deployment Requirements

## Backend runtime

Install:

```bash
pip install -r backend/requirements.txt
```

Required environment variables:

- `MONGO_USER`
- `MONGO_PASS`
- `MONGO_HOST_URI`
- `MONGO_DB_NAME`
- `MONGO_APP_NAME`
- `GEMINI_API_KEY` or `GEMINI_API_KEYS` or numbered `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, ...

Optional environment variables:

- `CONTEXT7_API_KEY`
- `VITE_API_BASE_URL` for the frontend when it talks to a deployed backend directly

Run the backend:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## Frontend build/runtime

Install:

```bash
cd frontend
npm install
```

Build for deployment:

```bash
npm run build
```

Frontend dependencies are already declared in `frontend/package.json`. The devDependencies are required for building, not for serving the built static assets.

## Notes

- The backend uses MongoDB-backed persistence for rules, approvals, budgets, logs, and chat state.
- The MCP local CRUD server is started by the backend process; no separate deploy step is needed for it.
- If you deploy the frontend as static files, point it at the backend with `VITE_API_BASE_URL` at build time.