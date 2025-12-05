from typing import Dict, Callable
from enum import Enum
from dataclasses import dataclass
from jobs.people_collector.schemas import WorkflowStatus
from threading import Lock

WORKFLOW_LOCK = Lock()

@dataclass
class WorkflowEntry:
    current_state: WorkflowStatus
    stop_flag: bool = False

# Keyed by jurisdiction id
RUNNING_WORKFLOWS: Dict[str, WorkflowEntry] = {}

def register_workflow(jurisdiction_id: str, current_state: WorkflowStatus):
    global RUNNING_WORKFLOWS

    with WORKFLOW_LOCK:
        RUNNING_WORKFLOWS[jurisdiction_id] = WorkflowEntry(
            current_state=current_state,
            stop_flag=False
        )

def update_workflow_state(jurisdiction_id: str, new_state: WorkflowStatus):
    global RUNNING_WORKFLOWS
    with WORKFLOW_LOCK:
        entry = RUNNING_WORKFLOWS.get(jurisdiction_id)
        if entry:
            entry.current_state = new_state
  
def stop_workflow(jurisdiction_id: str):
    with WORKFLOW_LOCK:
        entry = RUNNING_WORKFLOWS.get(jurisdiction_id)
        if entry:
            entry.stop_flag = True

def unregister_workflow(jurisdiction_id: str):
    global RUNNING_WORKFLOWS
    with WORKFLOW_LOCK:
        if jurisdiction_id in RUNNING_WORKFLOWS:
            del RUNNING_WORKFLOWS[jurisdiction_id]

def workflow_stop_requested(jurisdiction_id: str) -> bool:
    global RUNNING_WORKFLOWS
    entry = RUNNING_WORKFLOWS.get(jurisdiction_id)
    if entry:
        return entry.stop_flag
    return False

def list_workflows() -> Dict[str, WorkflowEntry]:
    with WORKFLOW_LOCK:
        return dict(RUNNING_WORKFLOWS)  # return a shallow copy

def get_workflow(jurisdiction_id: str) -> WorkflowEntry | None:
    global RUNNING_WORKFLOWS
    return RUNNING_WORKFLOWS.get(jurisdiction_id)