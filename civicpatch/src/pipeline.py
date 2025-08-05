import os
import json
from enum import Enum
import utils.data_path_utils as data_path_utils
from steps.step_01_collecting import collect
from steps.step_02_preprocessing import preprocess
from steps.step_03_processing import process
from steps.step_04_validation import validate
from steps.step_05_reporting import report
from steps.step_06_submission import submit

class PipelineState(Enum):
    INIT = "INIT",
    COLLECT = "COLLECT"
    PREPROCESS = "PREPROCESS"
    PROCESS = "PROCESS"
    VALIDATE = "VALIDATE"
    SUBMIT = "SUBMIT"
    REPORT = "REPORT"
    RETRY = "RETRY"
    DONE = "DONE"

class Pipeline:
    def __init__(self, state=PipelineState.INIT, context=None):
        self.state = state
        self.context = context or {"state": None, "geoid": None, "data": {}}

    def save_context(self, state, geoid):
        """
        Save the current pipeline context to a file for persistence.
        """
        context_file_path = data_path_utils.get_pipeline_context_file_path(state, geoid)
        with open(context_file_path, "w") as f:
            json.dump(self.context, f)
        print("Pipeline context saved.")

    def load_context(self, state, geoid):
        """
        Load the pipeline context from a file.
        """
        context = {}
        try:
            context_file_path = data_path_utils.get_pipeline_context_file_path(state, geoid)
            with open(context_file_path, "r") as f:
                context = json.load(f)
            print("Pipeline context loaded.")
        except FileNotFoundError:
            print("No saved context found. Starting fresh.")
            context = {"state": state, "geoid": geoid, "data": {}}
            
            os.makedirs(os.path.dirname(context_file_path), exist_ok=True)
            with open(context_file_path, "w") as f:
                json.dump(context, f, indent=4)
        
        return context
        
    def run(self, state, geoid):
        """
        Main function to run the pipeline for a given state and geoid.
        """
        self.context = self.load_context(state, geoid)

        while self.state != PipelineState.DONE:
            print(f"Running pipeline for state: {state}, geoid: {geoid}, current step: {self.state}")
            if self.state == PipelineState.COLLECT:
                self.context["data"]["collected"] = collect.collect(state, geoid)
                self.state = PipelineState.PREPROCESS

            elif self.state == PipelineState.PREPROCESS:
                self.context["data"]["preprocessed"] = preprocess.preprocess(self.context["data"]["collected"])
                self.state = PipelineState.PROCESS

            elif self.state == PipelineState.PROCESS:
                self.context["data"]["processed"] = process.process(self.context["data"]["preprocessed"])
                self.state = PipelineState.VALIDATE

            elif self.state == PipelineState.VALIDATE:
                validated = validate.validate(self.context["data"]["processed"])
                self.context["data"]["validated"] = validated
                if validated.get("is_valid", True):
                    print("Data validation passed.")
                    self.state = PipelineState.REPORT
                else:
                    print("Data validation failed. Moving onto next step...")
                    # self.state = PipelineState.RETRY
                    # TODO: maybe implement retry, but let's just skip to
                    # submission so human in the loop can fix it
                    self.state = PipelineState.REPORT


            elif self.state == PipelineState.REPORT:
                self.context["data"]["reported"] = report.report(self.context["data"]["validated"])
                self.state = PipelineState.SUBMIT

            elif self.state == PipelineState.SUBMIT:
                self.context["data"]["submitted"] = submit.submit(self.context["data"]["reported"])
                self.state = PipelineState.DONE
            
            elif self.state == PipelineState.RETRY:
                print("Retrying pipeline...")
                self.state = PipelineState.COLLECT
            else:
                print("Pipeline logic not yet implemented.")
                self.state = PipelineState.DONE

            # Save the context after each step
            self.save_context(state, geoid)

        print("Pipeline completed successfully.")
