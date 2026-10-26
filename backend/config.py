import os

HOST = "0.0.0.0"
PORT = 8000

# Path to local events storage
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVENTS_FILE_PATH = os.path.join(DATA_DIR, "events.json")

DEMO_DRIVER_ID = "DRV001"
DEMO_DRIVER_NAME = "Prototype Driver (Demo Test)"
DEMO_VEHICLE_ID = "VEH001"
DEMO_VEHICLE_NO = "Prototype Vehicle (Cabin Rig)"
