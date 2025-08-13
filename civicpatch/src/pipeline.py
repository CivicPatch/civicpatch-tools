import os
import json
from schemas import PipelineContext, PipelineStatus, LinkStatus, SearchEngineStatus

import utils.data_path_utils as data_path_utils
import utils.config_utils as config_utils
from steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from steps.step_01_research_municipality.research_municipality import research_municipality
from steps.step_02_search_links.search_links import search_links
from steps.step_03_scrape_page.scrape_page import scrape_page
from steps.step_04_preprocess_page_content.preprocess_page_content import preprocess_page_content
from steps.step_05_process_page_content.process_page_content import process_page_content
from steps.step_06_merge_records_within_source.merge_records_within_source import merge_records_within_source
from steps.step_07_merge_records_across_sources.merge_records_across_sources import merge_records_across_sources
from steps.step_08_send_to_github.send_to_github import send_to_github
from steps.step_09_cleanup.cleanup import cleanup

DEFAULT_STATE: PipelineContext = { 
    "links": [], 
    "progress": {
        "required_data": 5, # Default number of council members
        "current_data": 0,
    },
    "steps": {
        PipelineStatus.INIT.value: {},
        PipelineStatus.RESEARCH_MUNICIPALITY.value: {},
        PipelineStatus.SEARCH_LINKS.value: {
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
            "google_gemini": {},
            "openai": {}
        },
        PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE.value: {},
        PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES.value: {},
        PipelineStatus.SEND_TO_GITHUB.value: {},
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
    

    def get_links(self, status: LinkStatus, require_contact_page: bool = False):
        """
        Return all links with the given status.
        If require_contact_page is True, only return links where is_contact_page is True.
        """
        links = []
        for link in self.context["links"]:
            if link["status"] == status.value:
                if require_contact_page and not link.get("is_contact_page"):
                    continue
                links.append(link)
        return links

    def run(self, state, geoid):
        """
        Main function to run the pipeline for a given state and geoid.
        """
        self.context = self.load_context(state, geoid)
        process_config = config_utils.get_process()

        while self.state != PipelineStatus.DONE:
            if self.state == PipelineStatus.INIT:
                prepare_pipeline(self.context)
                self.state = PipelineStatus.RESEARCH_MUNICIPALITY

            elif self.state == PipelineStatus.RESEARCH_MUNICIPALITY:
                self.context.update(research_municipality(self.context))
                self.state = PipelineStatus.SEARCH_LINKS

            elif self.state == PipelineStatus.SEARCH_LINKS:
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
                preprocessed_links = self.get_links(LinkStatus.PREPROCESSED)
                links_processed = self.get_links(LinkStatus.DONE)
                process_max_pages = process_config.get("max_pages", 15)

                if not preprocessed_links:
                    print("No preprocessed links left to process.")
                    self.state = PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE
                    continue

                # Separate contact and non-contact pages
                contact_pages = [l for l in preprocessed_links if l.get("is_contact_page")]
                non_contact_pages = [l for l in preprocessed_links if not l.get("is_contact_page")]

                # Count how many non-contact pages have already been processed
                non_contact_processed = len([l for l in links_processed if not l.get("is_contact_page")])

                # Decide what to process next
                if contact_pages:
                    page_to_process = contact_pages[0]
                elif non_contact_pages and (non_contact_processed < process_max_pages):
                    page_to_process = non_contact_pages[0]
                else:
                    print("Max non-contact pages reached or no preprocessed links left to process.")
                    self.state = PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE
                    continue

                # Process the selected page
                self.context.update(process_page_content(self.context, page_to_process))
                print("Current data:", self.context["progress"]["current_data"])
                print("Required data:", self.context["progress"]["required_data"])

                # Refresh preprocessed_links after processing
                preprocessed_links = self.get_links(LinkStatus.PREPROCESSED)

                # Decide next state
                if preprocessed_links and preprocessed_links[0].get("is_contact_page"):
                    print(f"Next step: scrape website contact pages ({len(preprocessed_links)})...")
                    self.state = PipelineStatus.SCRAPE_PAGE
                elif (non_contact_processed + 1) >= process_max_pages:
                    print(f"Max non-contact pages ({process_max_pages}) reached, moving to next step...")
                    self.state = PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE
                elif self.context["progress"]["current_data"] < self.context["progress"]["required_data"]:
                    print("Not enough data processed yet, collecting more data...")
                    self.state = PipelineStatus.SCRAPE_PAGE
                else:
                    print("Enough data processed, moving to report generation...")
                    self.state = PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE

            elif self.state == PipelineStatus.MERGE_RECORDS_WITHIN_SOURCE:
                self.context.update(merge_records_within_source(self.context))
                self.state = PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES

            elif self.state == PipelineStatus.MERGE_RECORDS_ACROSS_SOURCES:
                self.context.update(merge_records_across_sources(self.context))
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
