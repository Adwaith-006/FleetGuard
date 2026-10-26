# AI Driver Drowsiness & Behaviour Safety Monitoring System

An AI-powered driver monitoring and fleet safety platform designed to detect signs of driver drowsiness and unsafe behaviour, record safety events, and help fleet owners review driver and vehicle safety through a web dashboard.

## 1. Project Overview

This project combines computer vision, a Python monitoring engine, a FastAPI backend, and a React-based owner dashboard.

The system is designed to:
- Detect driver drowsiness using a camera.
- Identify yawning and potential mobile phone usage.
- Generate safety events with timestamps, duration, and severity.
- Send monitoring events to a backend.
- Display driver, vehicle, safety history, and analytics on an owner dashboard.
- Generate downloadable safety reports in PDF format.

**Development status:** The core monitoring and dashboard architecture is present in the repository. Verify each feature locally before treating it as production-ready. The Ollama/Gemma chatbot integration is a planned development task and must be completed and tested separately.

## 2. System Architecture

```text
Camera Input
     |
     v
Python AI Monitoring Engine
     |
     +--> Drowsiness Detection
     +--> Face Detection
     +--> Yawning Detection
     +--> Phone Detection
     |
     v
Safety Event Manager
     |
     v
FastAPI Backend
     |
     +--> REST API
     +--> WebSocket Communication
     +--> Event Storage
     |
     v
React Owner Dashboard
     |
     +--> Driver and Vehicle Details
     +--> Safety History and Analytics
     +--> Reports and PDF Downloads
```

The AI monitoring engine processes camera frames and produces safety events. The backend receives and stores events, while the frontend provides the interface for fleet owners to review monitoring results.

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python | AI monitoring engine and event processing |
| OpenCV | Camera access and image processing |
| MediaPipe | Facial landmark detection, if used by the configured detector |
| YOLO | Object detection, including potential phone detection |
| FastAPI | Backend APIs |
| WebSockets | Live event communication |
| React | Owner dashboard interface |
| Vite | Frontend development server and build tooling |
| JavaScript and CSS | Dashboard functionality and styling |
| Ollama / Gemma | Planned local LLM integration |

The actual model and library usage depends on the implementation and configuration of each module.

## 4. Project Structure

```text
DriverDrowsinessDetection/
|
|-- main.py                 # Main AI monitoring application
|-- requirements.txt        # Python dependencies
|-- alarm.mp3               # Local alarm audio
|-- yolov8n.pt              # YOLO model weights, if downloaded
|-- .gitignore              # Files excluded from Git
|-- README.md               # Project documentation
|
|-- alerts/
|   |-- alarm_manager.py    # Alarm handling
|
|-- backend/
|   |-- main.py             # FastAPI application
|   |-- config.py           # Backend configuration
|   |-- models.py           # Backend data models
|   |-- storage.py          # Event storage operations
|   |-- websocket.py        # WebSocket handling
|   |-- requirements.txt    # Backend dependencies
|
|-- config/
|   |-- settings.py         # Monitoring configuration
|
|-- data/
|   |-- events_backup.json  # Existing event backup/sample data
|
|-- detection/
|   |-- drowsiness_detector.py
|   |-- face_detector.py
|   |-- phone_detector.py
|   |-- yawn_detector.py
|
|-- models/
|   |-- events.py           # Safety event structures
|
|-- monitoring/
|   |-- event_manager.py    # Safety event management
|   |-- session_manager.py  # Monitoring sessions
|   |-- severity_manager.py # Severity classification
|
|-- sync/
|   |-- api_client.py       # Backend communication client
|
|-- utils/
|   |-- logger.py           # Logging utilities
|   |-- visualizer.py       # Monitoring visualizations
|
|-- owner_dashboard/
    |-- package.json
    |-- vite.config.js
    |-- src/
        |-- components/
        |-- context/
        |-- pages/
        |-- services/
        |-- utils/
```

## 5. Prerequisites

Install the following software before running the project:

- Python 3.10 or a compatible version supported by the project's dependencies.
- Node.js and npm.
- Git.
- VS Code or another code editor.
- A working webcam.
- Ollama only if you are developing the local LLM integration.

Check your installations:

```bash
python --version
pip --version
node --version
npm --version
git --version
```

## 6. Clone the Repository

Open a terminal and run:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd DriverDrowsinessDetection
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with the HTTPS URL of this repository.

## 7. Set Up the Python Environment

From the project root, create and activate a virtual environment.

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt instead:

```bat
venv\Scripts\activate.bat
```

Install the root dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the backend has additional dependencies, install them as well:

```bash
pip install -r backend/requirements.txt
```

If a dependency installation fails, check its Python-version and operating-system requirements before changing package versions.

## 8. Download the Required YOLO Model

The `.pt` model weights are excluded from this Git repository by `.gitignore`.

If the application expects `yolov8n.pt`, download the corresponding official YOLOv8 nano model using the Ultralytics package:

```bash
pip install ultralytics
```

Then, from the project root:

```bash
yolo predict model=yolov8n.pt source=0
```

This example invokes YOLO prediction on the webcam and is intended to verify that the model can load. It is not a replacement for running the project's complete monitoring application.

If your configured code downloads the model automatically, follow the model-loading logic in that code instead. Place the weights at the path expected by the application.

## 9. Run the AI Monitoring Engine

Open a terminal in the project root, activate the virtual environment, and run:

```bash
python main.py
```

The monitoring engine is intended to access the webcam, process frames, detect configured unsafe behaviours, and generate safety events.

Before testing:
- Close other applications that are using the webcam.
- Allow camera access in Windows privacy settings.
- Confirm that the required model weights are available.
- Check the configuration if the camera index or model path differs on your machine.

Use a stationary test setup. Do not test drowsiness detection while driving a real vehicle.

## 10. Run the FastAPI Backend

Open a **separate terminal** in the project root and activate the same virtual environment.

Try:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

If the application cannot be imported using this module path, inspect the imports and entry-point configuration in `backend/main.py` and use the appropriate module path.

When the server starts successfully, open:

- API documentation: http://127.0.0.1:8000/docs
- Local API root: http://127.0.0.1:8000/

The root URL may not return a page unless a root endpoint has been implemented. The `/docs` page is available when FastAPI's interactive documentation is enabled.

The monitoring engine and backend must use matching API endpoints and configuration for telemetry to work correctly.

## 11. Run the React Owner Dashboard

Open another terminal:

```bash
cd owner_dashboard
npm install
npm run dev
```

Vite will print the local development URL in the terminal. Open that URL in your browser; it is commonly http://localhost:5173.

If the dashboard cannot connect to the backend, check the API base URL and WebSocket URL in the frontend configuration and service files. Make sure they match the backend address and port.

The dashboard may include sample data or UI components that still need to be connected to live backend responses.

## 12. Planned Ollama / Gemma Integration

The intended next step is to add a local AI assistant to the owner dashboard.

Possible responsibilities include:
- Summarizing driver safety events.
- Explaining safety reports in natural language.
- Answering questions about recorded monitoring data.
- Helping fleet owners interpret historical safety metrics.

Install Ollama separately and download a compatible model. For example:

```bash
ollama pull gemma3
ollama run gemma3
```

The commands above demonstrate how to download and run a model; they do not, by themselves, integrate it into this project.

To complete the integration, the application will need an appropriate backend service that calls Ollama, API endpoints for chatbot requests, and a frontend chat interface. Any answers based on fleet records should use actual stored data rather than fabricated model responses.

Model availability, RAM requirements, and response speed depend on the chosen model and hardware.

## 13. Configuration and Security

- Never commit `.env` files, API keys, OAuth credentials, JWT secrets, or access tokens.
- Use `.env.example` for placeholder configuration values.
- Do not upload real driver records or sensitive event logs to a public repository.
- Keep downloaded model weights and large datasets outside Git unless there is a specific reason to distribute them.
- Configure the backend and frontend endpoints for the local machine before testing.
- Use authentication and authorization before exposing owner dashboard data outside a local development environment.

## 14. Troubleshooting

**Camera does not open**
- Check Windows camera permissions.
- Close applications using the webcam.
- Verify the camera index and OpenCV installation.

**YOLO model not found**
- Download the required weights and check the path expected by the detection code.

**FastAPI import error**
- Activate the correct virtual environment.
- Install the dependencies.
- Check the module path and imports.

**Dashboard cannot reach the backend**
- Start the backend.
- Check API and WebSocket URLs.
- Inspect browser developer tools and backend terminal logs.

**Ollama connection error**
- Install and start Ollama.
- Confirm the model is downloaded.
- Check the configured model name and local API endpoint.

**Missing Python or npm packages**
- Install the relevant requirements or run `npm install` inside `owner_dashboard`.

## 15. Current Development Goals

1. Verify that each detection module works correctly with the webcam.
2. Improve detection stability and reduce false positives.
3. Verify that safety events reach the FastAPI backend.
4. Connect dashboard pages to live backend data.
5. Validate driver and vehicle reports and PDF generation.
6. Integrate Ollama/Gemma through a backend chatbot service.
7. Test the complete workflow on a clean computer.

## 16. Contributing

To contribute:

1. Clone the repository.
2. Create a separate Git branch for your changes.
3. Install the required dependencies.
4. Implement and test your changes locally.
5. Commit your changes and push the branch.
6. Open a pull request for review.

---

**Project:** AI Driver Drowsiness & Behaviour Safety Monitoring System  
**Purpose:** Driver safety monitoring and fleet-owner reporting  
**Status:** Development and integration in progress
