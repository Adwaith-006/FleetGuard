# AI Fleet Driver Behaviour & Safety Monitoring Platform

An enterprise-grade, edge-to-owner commercial fleet safety platform organized into two independent, decoupled services:

1. **Driver Monitoring Service (`driver_service`):** Runs on the driver's vehicle edge device/laptop. Monitors the driver via webcam or video, calculates geometric Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR) with MediaPipe Face Mesh, detects phone distractions with YOLOv8, detects head-down/lay-down postures, sounds immediate local audio alarms independently of the network, and queues telemetry to the owner service via a non-blocking background retry queue.
2. **Owner Management Service (`owner_service`):** Runs on the fleet administrator's server or workstation. Implemented with **FastAPI + MongoDB (PyMongo) + React (Vite) + local Gemma via Ollama**. Persists fleet drivers, drowsiness events, and AI analyses in MongoDB, broadcasts live alerts over WebSockets, and delivers structured advisory risk explanations using local Gemma.

---

## 1. Project Architecture

```text
Driver-Drowsiness-Safety-Monitoring/
│
├── driver_service/              # Service 1: Edge Driver Monitoring
│   ├── main.py                  # Driver service single-command entry point
│   ├── camera/                  # Webcam capture & video file fallback
│   ├── detection/               # FaceMesh, EAR/MAR fatigue, phone & posture detectors
│   ├── monitoring/              # Event lifecycle, state transitions, session manager
│   ├── alerts/                  # Local Pygame alarm & winsound fallback (100% offline)
│   ├── models/                  # Driver-side event schemas
│   ├── utils/                   # HUD visualizer, logger & async retry API client
│   ├── config/                  # Settings and .env threshold configuration
│   ├── assets/                  # Local alarm sound (alarm.mp3) & YOLO weights (yolov8n.pt)
│   ├── tests/                   # Automated unit test suite (16 tests)
│   ├── requirements.txt         # Driver service Python dependencies
│   └── README.md                # Driver service documentation
│
├── owner_service/               # Service 2: Fleet Management Platform
│   ├── backend/                 # FastAPI REST API & WebSocket server
│   │   ├── main.py              # Backend entry point
│   │   ├── routes/              # /api/health, /api/drivers, /api/events, /api/ai endpoints
│   │   ├── models/              # Pydantic request/response schemas
│   │   ├── services/            # EventService coordinating persistence & AI analysis
│   │   ├── database.py          # MongoDB persistence layer via PyMongo
│   │   ├── websocket.py         # Real-time WebSocket manager (/ws/events, /ws)
│   │   ├── tests/               # Backend test suite (10 unit & integration tests)
│   │   └── requirements.txt     # Backend Python dependencies
│   ├── frontend/                # React (Vite) Owner Dashboard
│   │   ├── src/                 # Components, pages, WebSocket consumer, dataService
│   │   ├── package.json         # Frontend Node.js dependencies
│   │   └── vite.config.js       # Vite build & proxy configuration
│   ├── ai/                      # Local AI Explanation Engine
│   │   └── gemma_service.py     # Ollama / Gemma integration (model: gemma4:e4b)
│   └── README.md                # Owner service documentation
│
├── shared/                      # Shared Contracts
│   └── event_schema.py          # Canonical SafetyEvent definition & status classifier
│
├── data/                        # Persistent buffers (Git-ignored)
│   └── events.json              # Local JSON buffer
│
├── .env.example                 # Environment configuration template
├── requirements.txt             # Root requirements pointing to both services
└── README.md                    # System documentation (this file)
```

---

## 2. Environment Setup (Windows PowerShell)

### Step 1: Start MongoDB
Ensure MongoDB Server is running on port 27017:
```powershell
# Check MongoDB Windows Service status
Get-Service MongoDB

# Start MongoDB service if stopped:
Start-Service MongoDB

# Or run mongod directly:
mongod --dbpath="C:\data\db"
```
- MongoDB URI: `mongodb://127.0.0.1:27017`
- Database Name: `driver_safety_db`
- Collections: `drivers`, `drowsiness_events`, `ai_analyses`

### Step 2: Start Local Ollama with Gemma
1. Open PowerShell and verify Ollama is installed:
```powershell
ollama list
```
*(The local installation includes `gemma4:e4b` or models like `gemma:2b`)*.
2. Start the Ollama background daemon:
```powershell
ollama serve
```

### Step 3: Install Python Dependencies
```powershell
# Backend Dependencies (Python 3.10 / 3.11)
pip install -r owner_service/backend/requirements.txt

# Driver Service Dependencies (Python 3.11 / 3.12)
pip install -r driver_service/requirements.txt
```

---

## 3. Running the Owner Management Service

### Step 1: Start the FastAPI Owner Backend
In a PowerShell terminal:
```powershell
python -m uvicorn owner_service.backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- Swagger API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### Step 2: Start the React Dashboard
In a **second PowerShell terminal**:
```powershell
cd owner_service/frontend
npm install
npm run dev
```
- Open in browser: [http://localhost:5173](http://localhost:5173)

---

## 4. Running the Driver Monitoring Service

In a **third PowerShell terminal**:
```powershell
python driver_service/main.py
```
- Press **`q`** in the video display window to stop and view the session summary.
- The driver service runs **completely offline**: the local Pygame audio alarm triggers immediately on eye closure without waiting for any network response or LLM inference.
- Events are transmitted in the background via a non-blocking queue to `http://127.0.0.1:8000/api/events`.

---

## 5. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health of the backend, MongoDB connection status (with version), and Ollama/Gemma availability. |
| `GET` | `/api/drivers` | Driver fleet list, vehicle assignments, alert status, and event counters. |
| `POST` | `/api/events` | Validates incoming driver events, persists them to MongoDB, and broadcasts over WebSockets. |
| `GET` | `/api/events` | Persisted events with pagination (`limit`, `skip`) and filters (`driver_id`, `severity`, `event_type`). |
| `GET` | `/api/events/{event_id}` | Retrieves a single event and its quantitative telemetry by ID. |
| `POST` | `/api/ai/analyze` | Triggers structured Gemma analysis on a stored event via Ollama. |
| `GET` | `/api/ai/analyses` | Retrieves stored Gemma analyses from MongoDB `ai_analyses`. |
| `GET` | `/api/ai/status` | Current Ollama connection status and installed local model tags. |
| `WS` | `/ws/events` | Real-time WebSocket event broadcast to connected dashboard clients. |
| `WS` | `/ws` | WebSocket endpoint alias. |

---

## 6. Running Automated Tests

### Owner Backend Tests (MongoDB, REST APIs, WebSockets, Ollama Error Handling)
```powershell
pytest owner_service/backend/tests -v
```
*(All 10 unit and integration tests execute with in-memory `mongomock` or live MongoDB)*.

### Driver Monitoring Service Tests (Computer Vision, EAR, Cooldowns, Alarms)
```powershell
pytest driver_service/tests -v
```
*(All 16 unit tests validate detection logic, geometry, posture, and alarms)*.
