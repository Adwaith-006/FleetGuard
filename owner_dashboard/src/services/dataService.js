// Data service providing driver profiles, vehicle data, and safety events

export const MOCK_DRIVERS = [
  {
    id: "DRV001",
    name: "Prototype Driver (Demo Test)",
    vehicleId: "VEH001",
    vehicleNo: "Prototype Vehicle (Cabin Rig)",
    phone: "+91 98765 43210",
    license: "DL-DEMO-2026",
    experience: "Prototype Evaluation",
    status: "ACTIVE"
  },
  {
    id: "DRV002",
    name: "Rajesh Sharma (Prototype Fleet)",
    vehicleId: "VEH002",
    vehicleNo: "TN45BC5678",
    phone: "+91 98123 45678",
    license: "DL-452190-B",
    experience: "5 years",
    status: "OFF_DUTY"
  },
  {
    id: "DRV003",
    name: "Suresh Patel (Prototype Fleet)",
    vehicleId: "VEH003",
    vehicleNo: "TN11CD9012",
    phone: "+91 97654 32109",
    license: "DL-118943-C",
    experience: "12 years",
    status: "OFF_DUTY"
  }
];

export const MOCK_VEHICLES = [
  {
    id: "VEH001",
    vehicleNo: "Prototype Vehicle (Cabin Rig)",
    model: "College Demo AI Test Rig",
    driverId: "DRV001",
    driverName: "Prototype Driver (Demo Test)",
    status: "ON_ROAD"
  },
  {
    id: "VEH002",
    vehicleNo: "TN45BC5678",
    model: "Tata 16-Ton Cargo Lorry (Sample)",
    driverId: "DRV002",
    driverName: "Rajesh Sharma (Prototype Fleet)",
    status: "PARKED"
  },
  {
    id: "VEH003",
    vehicleNo: "TN11CD9012",
    model: "Ashok Leyland Express Truck (Sample)",
    driverId: "DRV003",
    driverName: "Suresh Patel (Prototype Fleet)",
    status: "PARKED"
  }
];

export async function fetchEvents() {
  try {
    const response = await fetch("/api/events");
    if (response.ok) {
      const data = await response.json();
      if (Array.isArray(data)) {
        return data.map((evt) => ({
          ...evt,
          driver_id: evt.driver_id || "DRV001",
          driver_name: evt.driver_name || "Prototype Driver (Demo Test)",
          vehicle_id: evt.vehicle_id || "VEH001",
          vehicle_no: evt.vehicle_no || "Prototype Vehicle (Cabin Rig)"
        }));
      }
    }
  } catch (err) {
    console.warn("Could not fetch live events from API:", err);
  }

  // Never silently insert sample events into real safety history or reports
  return [];
}
