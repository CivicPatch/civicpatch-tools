import os
from utils import data_path_utils
import threading
from datetime import datetime

_PIPELINE_LOGGER_LOCK = threading.Lock()
_PIPELINE_LOG_FILES = {}
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class PipelineLogger:
    def __init__(self, jurisdiction_id: str):
        self.jurisdiction_id = jurisdiction_id
        log_path = get_pipeline_log_path(jurisdiction_id)
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


def get_pipeline_log_path(jurisdiction_id: str) -> str:
    data_source_municipality_path = data_path_utils.get_data_source_municipality_path(jurisdiction_id)
    os.makedirs(data_source_municipality_path, exist_ok=True)
    return f"{data_source_municipality_path}/pipeline.log"


def get_pipeline_logger(jurisdiction_id: str) -> PipelineLogger:
    with _PIPELINE_LOGGER_LOCK:
        if jurisdiction_id in _PIPELINE_LOG_FILES:
            return _PIPELINE_LOG_FILES[jurisdiction_id]

        logger = PipelineLogger(jurisdiction_id)
        _PIPELINE_LOG_FILES[jurisdiction_id] = logger
        return logger

def cleanup_pipeline_logger(jurisdiction_id: str):
    with _PIPELINE_LOGGER_LOCK:
        logger = _PIPELINE_LOG_FILES.pop(jurisdiction_id, None)
    if logger:
        logger.close()