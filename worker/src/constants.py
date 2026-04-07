from enum import StrEnum


class RunMode(StrEnum):
    START = "start"
    RESUME = "resume"


class RunConclusion(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
