import os
import json
from schemas import PipelineContext, PipelineRequest, PipelineStatus, LinkStatus, SearchEngineStatus, Link, Person 
from typing import List
import yaml
import time
import asyncio
import aiofiles
import json
import os

from utils import data_path_utils, config_utils, log_utils, cost_utils, id_utils
from steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from steps.step_01_research_municipality.research_municipality import research_municipality
from steps.step_02_search_links.search_links import search_links
from steps.step_02_search_links.utils import SearchEngineNames
from steps.step_03_scrape_page.scrape_page import scrape_page
from steps.step_04_preprocess_page_content.preprocess_page_content import preprocess_page_content
from steps.step_05_process_page_content.process_page_content import process_page_content
from steps.step_06_merge_records_within_llm.merge_records_within_llm import merge_records_within_llm
from steps.step_07_merge_records_across_llms.merge_records_across_llms import merge_records_across_llms
from steps.step_08_maybe_send_to_github.maybe_send_to_github import maybe_send_to_github
from steps.step_09_cleanup.cleanup import cleanup

_PIPELINE_PROGRESS_BY_JURISDICTION_ID = {}

DEFAULT_STATE: PipelineContext = { 
    "state": PipelineStatus.INIT.value,
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
            "raw_records_by_llm": {},
            "records_by_llm": {
                "google_gemini": {},
                "openai": {},
                "together_ai": {},
            },
        },
        PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value: {},
        PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value: {},
        PipelineStatus.CLEANUP.value: {},
        PipelineStatus.RETRY.value: {},
        PipelineStatus.DONE.value: {},
    },
}

class Pipeline:
    def __init__(self, pipeline_state=PipelineStatus.INIT, context=DEFAULT_STATE):
        self.state = pipeline_state
        self.context: PipelineContext = context

    def set_state(self, state: PipelineStatus):
        """
        Set the pipeline to start at a specific state.
        """
        if state in PipelineStatus:
            self.state = state
            print(f"Pipeline state set to: {state}")
        else:
            raise ValueError(f"Invalid pipeline state: {state}")

    async def save_context(self):
        """Save context asynchronously without blocking"""
        jurisdiction_id = self.context["jurisdiction_id"]
        self.context["state"] = self.state.value
        context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
        
        async with aiofiles.open(context_file_path, "w") as f:
            await f.write(json.dumps(self.context, indent=4))

    def load_context(self, request_id: str, pipeline_request: PipelineRequest) -> PipelineContext:
        """
        Always create a new pipeline context and overwrite any existing file.
        """  
        # Ensure the directory exists
        jurisdiction_id = pipeline_request.jurisdiction_id
        context_file_path = data_path_utils.get_pipeline_context_file_path(pipeline_request.jurisdiction_id)
        os.makedirs(os.path.dirname(context_file_path), exist_ok=True)

        if os.path.exists(context_file_path):
            with open(context_file_path, "r") as f:
                existing_context = json.load(f)
                existing_request_id = existing_context["request_id"]

                if request_id == existing_request_id:
                    print(f"Found existing request id, loading existing context")
                    return existing_context

        context: PipelineContext = {
            "request_id": request_id,
            "jurisdiction_id": jurisdiction_id,
            "name": pipeline_request.name,
            "url": pipeline_request.url,
        }

        with open(context_file_path, "w") as f:
            json.dump(context, f, indent=4)
        print(f"{jurisdiction_id}/{request_id}: New pipeline context created and saved.")

        return context

    def cleanup(self):
        log_utils.cleanup_pipeline_logger(self.context["jurisdiction_id"])
    
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
    
    def run(self, request_id, pipeline_request: PipelineRequest):
        asyncio.run(self.run_async(request_id, pipeline_request))
    
    async def run_async(self, request_id, pipeline_request: PipelineRequest, with_debug = False):
        """
        Main function to run the pipeline for a given jurisdiction id.
        """
        self.context = self.load_context(request_id, pipeline_request)

        jurisdiction_id = self.context["jurisdiction_id"]
        logger = log_utils.get_pipeline_logger(jurisdiction_id)
        process_config = config_utils.get_process()

        start_time = time.time()

        logger.info(f"Pipeline started at {time.ctime(start_time)}")

        try:
            while self.state != PipelineStatus.DONE:
                if self.state == PipelineStatus.INIT:
                    context: PipelineContext = {
                        **self.context,
                        **DEFAULT_STATE,
                    }
                    result = prepare_pipeline(context)
                    self.context.update(result)
                    self.state = PipelineStatus.RESEARCH_MUNICIPALITY

                elif self.state == PipelineStatus.RESEARCH_MUNICIPALITY:
                    result = research_municipality(self.context)
                    self.context.update(result)
                    self.state = PipelineStatus.SEARCH_LINKS

                elif self.state == PipelineStatus.SEARCH_LINKS:
                    search_link_pointer = self.context["steps"][PipelineStatus.SEARCH_LINKS.value]["search_link_pointer"]
                    if search_link_pointer >= len(SearchEngineNames):
                        logger.info("All search engines have been processed.")
                        self.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                    else:
                        result = search_links(self.context)
                        self.context.update(result)
                        self.state = PipelineStatus.SCRAPE_PAGE

                elif self.state == PipelineStatus.SCRAPE_PAGE:
                    page_to_scrape = self.get_next_link(LinkStatus.PENDING)

                    if not page_to_scrape:
                        logger.info("No pending links left to scrape.")
                        self.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                        continue

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

                    link_status = self.get_link_status_by_url(page_to_preprocess["url"])

                    if link_status == LinkStatus.PREPROCESSED:
                        self.state = PipelineStatus.PROCESS_PAGE_CONTENT
                    else: # link_status == LinkStatus.PREPROCESSED_NO_CONTENT:
                        self.state = PipelineStatus.SCRAPE_PAGE

                elif self.state == PipelineStatus.PROCESS_PAGE_CONTENT:
                    result, processed_count = self.process_page_content_step(logger)
                    self.context.update(result)

                    context_progress = self.context["progress"]
                    current_data = context_progress.get("current_data", 0)
                    required_data = context_progress.get("required_data", 0)
                    minimum_required_data = max(required_data - 3, 1) # At least 1 person

                    logger.info(f"Current data: {current_data}")
                    logger.info(f"Required data: {required_data}")

                    logger.info(f"Minimum required data: {minimum_required_data}")
                    logger.info(f"Has target role: {context_progress.get('has_target_role', False)}")
                    logger.info(f"Has target divisions (if available): {context_progress.get('has_target_divisions', False)}")

                    process_max_pages = process_config.get("max_pages", 15)

                    next_state = self.get_next_state_for_process_page_content(
                        logger,
                        processed_count, 
                        process_max_pages,
                        current_data,
                        required_data,
                        minimum_required_data
                    )

                    self.state = next_state

                elif self.state == PipelineStatus.MERGE_RECORDS_WITHIN_LLM:
                    result = merge_records_within_llm(self.context)
                    self.context.update(result)
                    self.state = PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

                elif self.state == PipelineStatus.MERGE_RECORDS_ACROSS_LLMS:
                    result = merge_records_across_llms(self.context)
                    self.save_data(result["steps"][PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value]["people"])

                    self.context.update(result)
                    self.state = PipelineStatus.CLEANUP

                elif self.state == PipelineStatus.CLEANUP:
                    result = cleanup(self.context)

                    self.context.update(result)
                    self.state = PipelineStatus.MAYBE_SEND_TO_GITHUB

                elif self.state == PipelineStatus.MAYBE_SEND_TO_GITHUB:
                    cost_utils.log_costs(self.context["request_id"], self.context["jurisdiction_id"])
                    result = maybe_send_to_github(self.context)

                    self.context.update(result)
                    self.state = PipelineStatus.DONE
                else:
                    logger.error(f"Pipeline logic not yet implemented for state: {self.state}")
                    self.state = PipelineStatus.DONE

                # Save the context after each step
                self.context["state"] = self.state.value
                _PIPELINE_PROGRESS_BY_JURISDICTION_ID[jurisdiction_id] = self.state.value
                await self.save_context()

            end_time = time.time()
            pipeline_duration = end_time - start_time
            self.context.update({"pipeline_duration_seconds": pipeline_duration})
            logger.info(f"Pipeline completed successfully in {pipeline_duration:.2f} seconds.")
        finally:
            _PIPELINE_PROGRESS_BY_JURISDICTION_ID.pop(jurisdiction_id, None)
            self.cleanup()

    def process_page_content_step(self, logger):
        """
        Handle the PROCESS_PAGE_CONTENT pipeline step.
        Returns the updated context and the next state.
        """
        preprocessed_links = self.get_links(LinkStatus.PREPROCESSED)
        links_processed = self.get_links(LinkStatus.DONE)
        processed_count = len(links_processed)

        if len(preprocessed_links) == 0:
            logger.info("No preprocessed links left to process.")
            return {}, processed_count 

        page_to_process = preprocessed_links[0] 

        updated_context = process_page_content(self.context, page_to_process)

        return updated_context, processed_count

    def get_next_state_for_process_page_content(self,
                                                logger,
                                                processed_count: int, 
                                                max_pages: int,
                                                current_data: int,
                                                required_data: int,
                                                minimum_required_data: int,
                                                ) -> PipelineStatus:
        """
        Calculate the next state for the pipeline based on the current progress and processed count.
        """
        has_target_role = self.context["progress"].get("has_target_role", False)
        has_target_divisions = self.context["progress"].get("has_target_divisions", False) 

        if current_data >= minimum_required_data and has_target_role and has_target_divisions:
            logger.info("Enough data processed, moving to report generation...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_LLM

        max_pages_with_required_data = max_pages + required_data # Each person might have a profile page
        if processed_count >= max_pages_with_required_data:
            logger.info(f"Max pages ({max_pages_with_required_data}) reached, moving to next step...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_LLM

        logger.info(f"Not enough data processed yet, collecting more data... {processed_count}/{max_pages_with_required_data}")
        return PipelineStatus.SCRAPE_PAGE
    
    def save_data(self, found_serialized_people: List[Person]):
        """
        Save the processed people data to a file.
        """ 
        jurisdiction_id = self.context["jurisdiction_id"]
        jurisdiction_type = id_utils.parse_jurisdiction_id(jurisdiction_id).jurisdiction_type

        existing_data = data_path_utils.get_people(jurisdiction_id)
        existing_data[jurisdiction_type] = found_serialized_people
        people_file_path = data_path_utils.get_people_file_path(jurisdiction_id)
        if not os.path.exists(people_file_path):
            # Ensure the directory exists
            os.makedirs(os.path.dirname(people_file_path), exist_ok=True)

            with open(people_file_path, "w", encoding="utf-8") as f:
                existing_data = {jurisdiction_type: found_serialized_people}

        with open(people_file_path, "w", encoding="utf-8") as f:
            yaml.dump(existing_data, f, default_flow_style=False, sort_keys=False)

def get_pipeline_status_by_jurisdiction_id(jurisdiction_id):
    return _PIPELINE_PROGRESS_BY_JURISDICTION_ID.get(jurisdiction_id, None)