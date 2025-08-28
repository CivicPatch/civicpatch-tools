import os
import asyncio
import json
from schemas import PipelineContext, PipelineStatus, LinkStatus, SearchEngineStatus, Link, Person
from typing import Dict, Any, List
import yaml

import utils.data_path_utils as data_path_utils
import utils.config_utils as config_utils
from steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from steps.step_01_research_municipality.research_municipality import research_municipality
from steps.step_02_search_links.search_links import search_links
from steps.step_02_search_links.utils import SearchEngineNames
from steps.step_03_scrape_page.scrape_page import scrape_page
from steps.step_04_preprocess_page_content.preprocess_page_content import preprocess_page_content
from steps.step_05_process_page_content.process_page_content import process_page_content
from steps.step_06_merge_records_within_source.merge_records_within_source import merge_records_within_source
from steps.step_07_merge_records_across_sources.merge_records_across_sources import merge_records_across_sources
from steps.step_08_maybe_send_to_github.maybe_send_to_github import maybe_send_to_github
from steps.step_09_cleanup.cleanup import cleanup

DEFAULT_STATE: PipelineContext = { 
    "links": [], 
    "progress": {
        "required_data": 5, # Default number of council members
        "current_data": 0,
    },
    "names": {},
    "steps": {
        PipelineStatus.INIT.value: {},
        PipelineStatus.RESEARCH_MUNICIPALITY.value: {},
        PipelineStatus.SEARCH_LINKS.value: {
            "search_link_pointer": 0,
            "search_engines": {
                "google": {"status": SearchEngineStatus.NOT_STARTED.value}, # not_started, processing, completed, failed  
                "brave": {"status": SearchEngineStatus.NOT_STARTED.value},
                "serp": {"status": SearchEngineStatus.NOT_STARTED.value},
                "crawl": {"status": SearchEngineStatus.NOT_STARTED.value},
            },
        },
        PipelineStatus.SCRAPE_PAGE.value: {},
        PipelineStatus.PREPROCESS_PAGE_CONTENT.value: {},
        PipelineStatus.PROCESS_PAGE_CONTENT.value: { # Lists of people by names
            "records_by_source": {
                "google_gemini": {},
                "openai": {},
                "together_ai": {},
            },
        },
        PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value: {},
        PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES.value: {},
        PipelineStatus.CLEANUP.value: {},
        PipelineStatus.RETRY.value: {},
        PipelineStatus.DONE.value: {},
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

    def load_context(self, request_id: str, state: str, geoid: str) -> PipelineContext:
        """
        Always create a new pipeline context and overwrite any existing file.
        """
        context: PipelineContext = {
            **DEFAULT_STATE,
            "request_id": request_id,
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
    
    def get_link_status_by_url(self, url: str) -> LinkStatus:
        for link in self.context["links"]:
            if link["url"] == url:
                return LinkStatus(link["status"])
        return None

    def get_links(self, status: LinkStatus) -> List[Link]:
        """
        Return all links with the given status.
        """
        return [link for link in self.context["links"] if link["status"] == status.value]
    
    def run(self, request_id, state, geoid):
        asyncio.run(self.run_async(request_id, state, geoid))
    
    async def run_async(self, request_id, state, geoid):
        """
        Main function to run the pipeline for a given state and geoid.
        """
        self.context = self.load_context(request_id, state, geoid)
        process_config = config_utils.get_process()

        while self.state != PipelineStatus.DONE:
            if self.state == PipelineStatus.INIT:
                result = prepare_pipeline(self.context)
                self.context.update(result)
                self.state = PipelineStatus.RESEARCH_MUNICIPALITY

            elif self.state == PipelineStatus.RESEARCH_MUNICIPALITY:
                result = research_municipality(self.context)
                self.context.update(result)
                self.state = PipelineStatus.SEARCH_LINKS

            elif self.state == PipelineStatus.SEARCH_LINKS:
                search_link_pointer = self.context["steps"][PipelineStatus.SEARCH_LINKS.value]["search_link_pointer"]
                if search_link_pointer >= len(SearchEngineNames):
                    print("All search engines have been processed.")
                    self.state = PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE
                else:
                    result = search_links(self.context)
                    self.context.update(result)
                    self.state = PipelineStatus.SCRAPE_PAGE

            elif self.state == PipelineStatus.SCRAPE_PAGE:
                page_to_scrape = self.get_next_link(LinkStatus.PENDING)
                result = await scrape_page(self.context, page_to_scrape)
                self.context.update(result)

                link_status = self.get_link_status_by_url(page_to_scrape["url"])
                if link_status == LinkStatus.SCRAPED:
                    self.state = PipelineStatus.PREPROCESS_PAGE_CONTENT
                else:
                    self.state = PipelineStatus.SCRAPE_PAGE

            elif self.state == PipelineStatus.PREPROCESS_PAGE_CONTENT:
                page_to_preprocess = self.get_next_link(LinkStatus.SCRAPED)
                result = preprocess_page_content(self.context, page_to_preprocess)
                self.context.update(result)
                self.state = PipelineStatus.PROCESS_PAGE_CONTENT

            elif self.state == PipelineStatus.PROCESS_PAGE_CONTENT:
                result, processed_count, process_max_pages = self.process_page_content_step(process_config)
                self.context.update(result)

                print("Current data:", result["progress"]["current_data"])
                print("Required data:", result["progress"]["required_data"])

                next_state = self.get_next_state_for_process_page_content(processed_count, process_max_pages)
                self.state = next_state

            elif self.state == PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE:
                result = merge_records_within_source(self.context)
                self.context.update(result)
                self.state = PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES

            elif self.state == PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES:
                result = merge_records_across_sources(self.context)
                self.save_data(result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES.value]["people"])
                
                self.context.update(result)
                self.state = PipelineStatus.MAYBE_SEND_TO_GITHUB

            elif self.state == PipelineStatus.MAYBE_SEND_TO_GITHUB:
                result = maybe_send_to_github(self.context)

                print("what is result", result)
                self.context.update(result)
                self.state = PipelineStatus.DONE

            else:
                print("Pipeline logic not yet implemented.")
                self.state = PipelineStatus.DONE

            # Save the context after each step
            self.save_context(state, geoid)

        print("Pipeline completed successfully.")

    def process_page_content_step(self, process_config):
        """
        Handle the PROCESS_PAGE_CONTENT pipeline step.
        Returns the updated context and the next state.
        """
        preprocessed_links = self.get_links(LinkStatus.PREPROCESSED)
        links_processed = self.get_links(LinkStatus.DONE)
        process_max_pages = process_config.get("max_pages", 15)
        processed_count = len(links_processed)

        if not preprocessed_links:
            print("No preprocessed links left to process.")
            return {}, processed_count, PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE


        page_to_process = preprocessed_links[0] if preprocessed_links and processed_count < process_max_pages else None
        if not page_to_process:
            print("Max pages reached or no preprocessed links left to process.")
            return {}, processed_count, PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE

        updated_context = process_page_content(self.context, page_to_process)

        return updated_context, processed_count, process_max_pages

    def get_next_state_for_process_page_content(self, processed_count: int, max_pages: int) -> PipelineStatus:
        """
        Calculate the next state for the pipeline based on the current progress and processed count.
        """
        if self.context["progress"]["current_data"] >= self.context["progress"]["required_data"]:
            print("Enough data processed, moving to report generation...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE

        if processed_count >= max_pages:
            print(f"Max pages ({max_pages}) reached, moving to next step...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE

        print("Not enough data processed yet, collecting more data...")
        return PipelineStatus.SCRAPE_PAGE
    
    def save_data(self, people: List[Person]):
        """
        Save the processed people data to a file.
        """
        state = self.context["state"]
        geoid = self.context["geoid"]
        data_municipality_path = data_path_utils.get_data_municipality_path(state, geoid)
        people_file_path = os.path.join(data_municipality_path, 'people.yml')

        # Ensure the directory exists
        os.makedirs(data_municipality_path, exist_ok=True)

        with open(people_file_path, "w") as f:
            yaml.dump([person for person in people], f, default_flow_style=False)
   