"""Shared lab service types and operation constraints."""

LAB_SERVER_TYPES = (
    "HL7 Engine",
    "FHIR Server",
    "EMR",
    "GDT Bridge",
    "DICOM Archive",
    "Test Tool",
    "Generic HTTP Service",
)
LAB_SERVER_PROTOCOLS = ("HTTP", "TCP", "MLLP", "FHIR", "GDT", "DICOM", "None")
LAB_HEALTH_STATUSES = ("Healthy", "Degraded", "Down", "Unknown")
LAB_OPERATION_ACTIONS = ("status", "start", "stop", "restart", "smoke", "logs")
