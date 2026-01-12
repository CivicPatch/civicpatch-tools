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

def register_workflow(jurisdiction_ocdid: str, current_state: WorkflowStatus):
    global RUNNING_WORKFLOWS

    with WORKFLOW_LOCK:
        RUNNING_WORKFLOWS[jurisdiction_ocdid] = WorkflowEntry(
            current_state=current_state,
            stop_flag=False
        )

def update_workflow_state(jurisdiction_ocdid: str, new_state: WorkflowStatus):
    global RUNNING_WORKFLOWS
    with WORKFLOW_LOCK:
        entry = RUNNING_WORKFLOWS.get(jurisdiction_ocdid)
        if entry:
            entry.current_state = new_state
  
def stop_workflow(jurisdiction_ocdid: str):
    with WORKFLOW_LOCK:
        entry = RUNNING_WORKFLOWS.get(jurisdiction_ocdid)
        if entry:
            entry.stop_flag = True

def unregister_workflow(jurisdiction_ocdid: str):
    global RUNNING_WORKFLOWS
    with WORKFLOW_LOCK:
        if jurisdiction_ocdid in RUNNING_WORKFLOWS:
            del RUNNING_WORKFLOWS[jurisdiction_ocdid]

def workflow_stop_requested(jurisdiction_ocdid: str) -> bool:
    global RUNNING_WORKFLOWS
    entry = RUNNING_WORKFLOWS.get(jurisdiction_ocdid)
    if entry:
        return entry.stop_flag
    return False

def list_workflows() -> Dict[str, WorkflowEntry]:
    with WORKFLOW_LOCK:
        return dict(RUNNING_WORKFLOWS)  # return a shallow copy

def get_workflow(jurisdiction_ocdid: str) -> WorkflowEntry | None:
    global RUNNING_WORKFLOWS
    return RUNNING_WORKFLOWS.get(jurisdiction_ocdid)