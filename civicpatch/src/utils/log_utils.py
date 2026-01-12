import os
from shared.utils import data_path_utils
import threading
from datetime import datetime

_WORKFLOW_LOGGER_LOCK = threading.Lock()
_WORKFLOW_LOG_FILES = {}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class WorkflowLogger:
    def __init__(self, jurisdiction_ocdid: str):
        self.jurisdiction_ocdid = jurisdiction_ocdid
        log_path = get_workflow_log_path(jurisdiction_ocdid)
        self.file = open(log_path, "a", encoding="utf-8")
        
    def _write(self, level: str, message: str):
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] [{level.upper()}] {message}\n"
        
        self.file.write(line)
        self.file.flush()
        
        # Optionally log out to console
        if os.getenv("LOG_TO_CONSOLE", "true").lower() == "true":
            print(line, end="")

    def debug(self, message: str):
        if LOG_LEVEL == "DEBUG":
            self._write("DEBUG", message)

    def warning(self, message: str):
        if LOG_LEVEL == "DEBUG":
            self._write("WARNING", message)
    
    def info(self, message: str):
        self._write("INFO", message)

    def error(self, message: str):
        self._write("ERROR", message)
    
    def clear(self):
        self.file.seek(0)      # Go to beginning of file
        self.file.truncate(0)  # Truncate to 0 bytes
        self.file.flush()      # Ensure it's written to disk

    def close(self):
        self.file.close()


def get_workflow_log_path(jurisdiction_ocdid: str) -> str:
    data_source_municipality_path = data_path_utils.get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    os.makedirs(data_source_municipality_path, exist_ok=True)
    return f"{data_source_municipality_path}/workflow.log"


def get_workflow_logger(jurisdiction_ocdid: str) -> WorkflowLogger:
    with _WORKFLOW_LOGGER_LOCK:
        if jurisdiction_ocdid in _WORKFLOW_LOG_FILES:
            return _WORKFLOW_LOG_FILES[jurisdiction_ocdid]

        logger = WorkflowLogger(jurisdiction_ocdid)
        _WORKFLOW_LOG_FILES[jurisdiction_ocdid] = logger
        return logger

def cleanup_workflow_logger(jurisdiction_ocdid: str):
    with _WORKFLOW_LOGGER_LOCK:
        logger = _WORKFLOW_LOG_FILES.pop(jurisdiction_ocdid, None)
    if logger:
        logger.close()