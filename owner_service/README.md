# Owner Management Service

The central fleet administrative and analytics platform for fleet owners and safety supervisors. Ingests real-time safety events from vehicles, persists them in **MongoDB** via PyMongo, streams live telemetry to a **React (Vite)** dashboard via WebSockets, and produces advisory risk analysis through locally hosted **Gemma via Ollama**.

---

## 1. Architecture

```text
Driver Monitoring Service (Edge Video AI)
        │
        ▼ (HTTP POST /api/events - Non-blocking bounded retry queue)
FastAPI Backend (port 8000)
   ├── MongoDB Database (driver_safety_db, port 27017)
   │     ├── drivers (roster, vehicle assignments, alert counters)
   │     ├── drowsiness_events (events, UTC datetimes, telemetry metrics)
   │     └── ai_analyses (structured Gemma advice, recommendations, audit link)
   │
   ├── WebSocket Broadcaster (/ws/events & /ws)
   │     ▼
   │   React Owner Dashboard (port 5173)
   │     - Live Safety Stream with reconnection
   │     - Fleet Score & Category KPIs
   │     - Monitored Driver Status Cards
   │     - Telemetry Metrics & On-Demand Gemma AI Analysis
   │     - Backend, MongoDB & Ollama connectivity badges
   │
   └── Local Gemma LLM (Ollama HTTP API, port 11434, model: gemma4:e4b)
         - Zero cloud API dependency; 100% private & local
         - Strictly telemetry-based; never receives raw camera frames
         - Advisory risk classification & practical management actions
```

---

## 2. Prerequisites & Installation

### A. MongoDB Setup
Ensure MongoDB Community Server is installed (v6.0+ / v7.0+ / v9.0+).

In **Windows PowerShell (Admin)**:
```powershell
# Check MongoDB Windows Service status
Get-Service MongoDB

# If stopped, start the service:
Start-Service MongoDB

# Or run mongod directly if running as standalone executable:
mongod --dbpath="C:\data\db"
```
Default connection string: `mongodb://127.0.0.1:27017`  
Database name: `driver_safety_db`

### B. Ollama & Gemma Setup
1. Download and install Ollama from [ollama.com](https://ollama.com/download).
2. Verify installed models in PowerShell:
```powershell
ollama list
```
*(The system automatically detects installed models such as `gemma4:e4b` or pulls models via `ollama pull gemma:2b` or `ollama pull gemma4:e4b`)*.
3. Start the Ollama server:
```powershell
ollama serve
```
*(If the Ollama Windows app is already running in your system tray, port `11434` is active automatically)*.

### C. Python Environment & Backend Dependencies
In Windows PowerShell (at repo root):
```powershell
# Using Python 3.11 virtual environment or system Python:
pip install -r owner_service/backend/requirements.txt
```

---

## 3. Quick Start (Windows PowerShell)

### Step 1: Start the FastAPI Backend
From the repository root:
```powershell
python -m uvicorn owner_service.backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Step 2: Start the React Dashboard
In a separate PowerShell terminal:
```powershell
cd owner_service/frontend
npm install
npm run dev
```
- Open in browser: `http://localhost:5173`

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Backend health, MongoDB connection status, and Ollama/Gemma availability. |
| `GET` | `/api/drivers` | Fleet drivers list with assigned vehicle, alert status, and event counters. |
| `POST` | `/api/events` | Ingests and persists safety event to MongoDB; broadcasts to WebSocket. |
| `GET` | `/api/events` | Paginated events (`limit`, `skip`) with optional filters (`driver_id`, `severity`, `event_type`). |
| `GET` | `/api/events/{event_id}` | Retrieves a single event and its quantitative telemetry by ID. |
| `POST` | `/api/ai/analyze` | Triggers structured Gemma analysis on a stored event via Ollama. |
| `GET` | `/api/ai/analyses` | Retrieves stored Gemma analyses from MongoDB `ai_analyses`. |
| `GET` | `/api/ai/status` | Current Ollama connection status and installed local model tags. |
| `WS` | `/ws/events` | Real-time WebSocket event stream for connected dashboard clients. |
| `WS` | `/ws` | WebSocket endpoint alias. |

---

## 5. Automated Tests

Run the test suite verifying MongoDB persistence, FastAPI endpoints, WebSocket broadcasting, and Ollama error handling:
```powershell
pytest owner_service/backend/tests -v
```
*(Tests use `mongomock` in-memory client for isolated unit verification, or live MongoDB)*.
