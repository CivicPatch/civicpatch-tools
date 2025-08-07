import os
import json
from schemas import PipelineContext, PipelineStatus, LinkStatus, SearchEngineStatus

import utils.data_path_utils as data_path_utils
from steps.step_01_search_links.search_links import search_links
from steps.step_02_scrape_page.scrape_page import scrape_page
from steps.step_03_preprocess_page_content.preprocess_page_content import preprocess_page_content
from steps.step_04_process_page_content.process_page_content import process_page_content
from steps.step_05_generate_report.generate_report import generate_report
from steps.step_06_send_to_github.send_to_github import send_to_github

DEFAULT_STATE: PipelineContext = {
    "search_engines": {
        "google": {"status": SearchEngineStatus.NOT_STARTED.value}, # not_started, processing, completed, failed  
        "brave": {"status": SearchEngineStatus.NOT_STARTED.value},
        "serp": {"status": SearchEngineStatus.NOT_STARTED.value},
        "crawl": {"status": SearchEngineStatus.NOT_STARTED.value},
    },
    "links": [],
    "steps": {
        PipelineStatus.INIT.value: {},
        PipelineStatus.SEARCH_LINKS.value: {},
        PipelineStatus.SCRAPE_PAGE.value: {},
        PipelineStatus.PREPROCESS_PAGE_CONTENT.value: {},
        PipelineStatus.PROCESS_PAGE_CONTENT.value: {},
        PipelineStatus.GENERATE_REPORT.value: {},
        PipelineStatus.SEND_TO_GITHUB.value: {},
        PipelineStatus.RETRY.value: {},
        PipelineStatus.DONE.value: {},
    },
    "progress": {
        "required_data": 5, # Default number of council members, for example
        "current_data": 0,
    },
}

class Pipeline:
    def __init__(self, pipeline_state=PipelineStatus.INIT, context=DEFAULT_STATE):
        self.state = pipeline_state
        self.context: PipelineContext = context

    def save_context(self, state, geoid):
        """
        Save the current pipeline context to a file for persistence.
        """
        context_file_path = data_path_utils.get_pipeline_context_file_path(state, geoid)
        with open(context_file_path, "w") as f:
            json.dump(self.context, f, indent=4)
        print("Pipeline context saved.")

    def load_context(self, state: str, geoid: str) -> PipelineContext:
        """
        Always create a new pipeline context and overwrite any existing file.
        """
        context: PipelineContext = {
            **DEFAULT_STATE,
            "state": state,
            "geoid": geoid
        }

        context_file_path = data_path_utils.get_pipeline_context_file_path(state, geoid)
        os.makedirs(os.path.dirname(context_file_path), exist_ok=True)
        with open(context_file_path, "w") as f:
            json.dump(context, f, indent=4)
        print("New pipeline context created and saved.")

        return context
    
    def get_next_link(self, status: LinkStatus):
        for link in self.context["links"]:
            if link["status"] == status.value:
                return link
        return None

    def run(self, state, geoid):
        """
        Main function to run the pipeline for a given state and geoid.
        """
        self.context = self.load_context(state, geoid)

        while self.state != PipelineStatus.DONE:
            print(f"Running pipeline for state: {state}, geoid: {geoid}, current step: {self.state}")
            if self.state == PipelineStatus.INIT:
                # TODO:
                # clear folder cache, create cache folder if not exists

                self.context = self.load_context(state, geoid)
                self.state = PipelineStatus.SEARCH_LINKS

            if self.state == PipelineStatus.SEARCH_LINKS:
                self.context.update(search_links(self.context))
                self.state = PipelineStatus.SCRAPE_PAGE

            elif self.state == PipelineStatus.SCRAPE_PAGE:
                page_to_scrape = self.get_next_link(LinkStatus.PENDING)
                self.context.update(scrape_page(self.context, page_to_scrape))
                self.state = PipelineStatus.PREPROCESS_PAGE_CONTENT

            elif self.state == PipelineStatus.PREPROCESS_PAGE_CONTENT:
                page_to_preprocess = self.get_next_link(LinkStatus.SCRAPED)
                self.context.update(preprocess_page_content(self.context, page_to_preprocess))
                self.state = PipelineStatus.PROCESS_PAGE_CONTENT

            elif self.state == PipelineStatus.PROCESS_PAGE_CONTENT:
                page_to_process = self.get_next_link(LinkStatus.PREPROCESSED)
                self.context.update(process_page_content(self.context, page_to_process))

                if self.context["progress"]["current_data"] < self.context["progress"]["required_data"]:
                    print("Not enough data processed yet, collecting more data...")
                    self.state = PipelineStatus.SCRAPE_PAGE
                else:
                    print("Enough data processed, moving to report generation...")
                    self.state = PipelineStatus.GENERATE_REPORT

            elif self.state == PipelineStatus.GENERATE_REPORT:
                self.context.update(generate_report(self.context))
                self.state = PipelineStatus.SEND_TO_GITHUB

            elif self.state == PipelineStatus.SEND_TO_GITHUB:
                self.context.update(send_to_github(self.context))
                self.state = PipelineStatus.DONE

            #elif self.state == PipelineStatus.RETRY:
            #    print("Retrying pipeline...")
            #    self.state = PipelineStatus.COLLECT
            else:
                print("Pipeline logic not yet implemented.")
                self.state = PipelineStatus.DONE

            # Save the context after each step
            self.save_context(state, geoid)

        print("Pipeline completed successfully.")
