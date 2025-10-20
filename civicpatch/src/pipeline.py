import os
import json
from pydantic.json import pydantic_encoder
from schemas import PipelineContext, PipelineRequest, PipelineStatus, LinkStatus, ProcessConfig, SearchEngineStatus, Link, Person, SearchLinksStep
from pydantic import ValidationError
from typing import List, cast
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

class Pipeline:
    def __init__(self, request_id, pipeline_request: PipelineRequest, remove_callback):
        self.context = self.load_context(request_id, pipeline_request)
        self.stop_requested = False
        self.remove_callback = remove_callback

    def set_state(self, new_state: PipelineStatus):
        self.context.state = new_state

    async def save_context(self):
        """Save context asynchronously without blocking"""
        jurisdiction_id = self.context.jurisdiction_id
        context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)

        print("Saving pipeline context to", context_file_path) 
        print("self.context set to", self.context.model_dump_json()[:50])
        try:
            async with aiofiles.open(context_file_path, "w") as f:
                serialized_context = self.context.model_dump_json(indent=4)
                print("serialized_context:", serialized_context[:50])
                await f.write(serialized_context)
        except Exception as e:
            print(f"Exception in save_context: {e}")

    def load_from_context_file(self, jurisdiction_id: str):
        context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)

        with open(context_file_path, "r") as f:
            context_data = json.load(f)
            context = PipelineContext.model_validate(context_data)
            return context


    def load_context(self, request_id: str, pipeline_request: PipelineRequest) -> PipelineContext:
        """
        Always create a new pipeline context and overwrite any existing file.
        """  
        # Ensure the directory exists
        jurisdiction_id = pipeline_request.jurisdiction_id
        context_file_path = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
        os.makedirs(os.path.dirname(context_file_path), exist_ok=True)

        if pipeline_request.state != PipelineStatus.INIT:
            existing_context = self.load_from_context_file(jurisdiction_id)
            existing_context.request_id = request_id
            if existing_context:
                print(f"{jurisdiction_id}/{request_id}: Loaded existing pipeline context for debugging.")
                existing_context.state = pipeline_request.state
                return existing_context

        context = PipelineContext(
            request_id=request_id,
            jurisdiction_id=jurisdiction_id,
            name=pipeline_request.name,
            url=pipeline_request.url
        )

        print(f"{jurisdiction_id}/{request_id}: New pipeline context created.")

        return context

    def cleanup(self):
        log_utils.cleanup_pipeline_logger(self.context.jurisdiction_id)
        if self.remove_callback:
            self.remove_callback(self.context.jurisdiction_id)
    
    def get_next_link(self, status: LinkStatus):
        for link in self.context.links:
            if link.status == status.value:
                return link
        return None
    
    def get_link_status_by_url(self, url: str) -> LinkStatus | None:
        for link in self.context.links:
            if link.url == url:
                return LinkStatus(link.status)
        return None

    def get_links(self, status: LinkStatus) -> List[Link]:
        """
        Return all links with the given status.
        """
        return [link for link in self.context.links if link.status == status.value]
    
    def run(self):
        asyncio.run(self.run_async())
    
    async def run_async(self, with_debug = False):
        """
        Main function to run the pipeline for a given jurisdiction id.
        """
        jurisdiction_id = self.context.jurisdiction_id
        logger = log_utils.get_pipeline_logger(jurisdiction_id)
        process_config = config_utils.get_process(logger)

        start_time = time.time()

        logger.info(f"Pipeline started at {time.ctime(start_time)}")

        try:
            while self.context.state not in [PipelineStatus.DONE]:
                if self.stop_requested:
                    self.context.state = PipelineStatus.DONE
                    logger.info("Pipeline stop requested. Exiting run loop.")

                if self.context.state == PipelineStatus.INIT:
                    prepare_pipeline(self.context)
                    self.context.state = PipelineStatus.RESEARCH_MUNICIPALITY

                elif self.context.state == PipelineStatus.RESEARCH_MUNICIPALITY:
                    result = research_municipality(self.context)
                    self.context.progress = result["progress"]
                    self.context.steps[PipelineStatus.RESEARCH_MUNICIPALITY] = result["result"]

                    self.context.state = PipelineStatus.SEARCH_LINKS

                elif self.context.state == PipelineStatus.SEARCH_LINKS:

                    if PipelineStatus.SEARCH_LINKS not in self.context.steps:
                        search_link_state = SearchLinksStep(
                            search_link_pointer=0,
                            search_engines={},
                            error=None
                        )
                    else:
                        search_link_state = self.context.steps[PipelineStatus.SEARCH_LINKS]
                        search_link_state = cast(SearchLinksStep, search_link_state)
                    search_link_pointer = search_link_state.search_link_pointer

                    if search_link_pointer >= len(SearchEngineNames):
                        logger.info("All search engines have been processed.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                    else:
                        result = search_links(self.context)
                        self.context.links = result["links"]
                        self.context.steps[PipelineStatus.SEARCH_LINKS] = result["result"]
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.SCRAPE_PAGE:
                    page_to_scrape = self.get_next_link(LinkStatus.PENDING)

                    if not page_to_scrape:
                        logger.info("No pending links left to scrape.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                        continue

                    result = await scrape_page(self.context, page_to_scrape)
                    self.context.links = result

                    link_status = self.get_link_status_by_url(page_to_scrape.url)
                    if link_status == LinkStatus.SCRAPED:
                        self.context.state = PipelineStatus.PREPROCESS_PAGE_CONTENT
                    else:
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.PREPROCESS_PAGE_CONTENT:
                    page_to_preprocess = self.get_next_link(LinkStatus.SCRAPED)
                    if not page_to_preprocess:
                        logger.info("No scraped links left to preprocess.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                        continue

                    result = preprocess_page_content(self.context, page_to_preprocess)
                    self.context.links = result["links"]
                    self.context.steps[PipelineStatus.PREPROCESS_PAGE_CONTENT] = result["result"]

                    link_status = self.get_link_status_by_url(page_to_preprocess.url)

                    if link_status == LinkStatus.PREPROCESSED:
                        self.context.state = PipelineStatus.PROCESS_PAGE_CONTENT
                    else: # link_status == LinkStatus.PREPROCESSED_NO_CONTENT:
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.PROCESS_PAGE_CONTENT:
                    result, processed_count = self.process_page_content_step(logger)
                    self.context.links = result["links"]
                    self.context.progress = result["progress"]
                    self.context.names = result["names"]
                    self.context.steps[PipelineStatus.PROCESS_PAGE_CONTENT] = result["result"]

                    context_progress = self.context.progress
                    current_data = context_progress.current_data
                    required_data = context_progress.required_data
                    minimum_required_data = max(required_data - 3, 1) # At least 1 person

                    logger.info(f"Current data: {current_data}")
                    logger.info(f"Required data: {required_data}")

                    logger.info(f"Minimum required data: {minimum_required_data}")
                    logger.info(f"Has target role: {context_progress.has_target_role}")
                    logger.info(f"Has target divisions (if available): {context_progress.has_target_divisions}")

                    next_state = self.get_next_state_for_process_page_content(
                        logger,
                        processed_count, 
                        process_config,
                        current_data,
                        required_data,
                        minimum_required_data
                    )

                    self.context.state = next_state

                elif self.context.state == PipelineStatus.MERGE_RECORDS_WITHIN_LLM:
                    result = merge_records_within_llm(self.context)
                    self.context.steps[PipelineStatus.MERGE_RECORDS_WITHIN_LLM] = result
                    self.context.state = PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

                elif self.context.state == PipelineStatus.MERGE_RECORDS_ACROSS_LLMS:
                    result = merge_records_across_llms(self.context)
                    self.save_data(result.people)
                    self.context.steps[PipelineStatus.MERGE_RECORDS_ACROSS_LLMS] = result
                    self.context.state = PipelineStatus.CLEANUP

                elif self.context.state == PipelineStatus.CLEANUP:
                    result = cleanup(self.context)

                    self.context.state = PipelineStatus.MAYBE_SEND_TO_GITHUB

                elif self.context.state == PipelineStatus.MAYBE_SEND_TO_GITHUB:
                    cost_utils.log_costs(self.context.request_id, self.context.jurisdiction_id)
                    result = maybe_send_to_github(self.context)

                    self.context.state = PipelineStatus.DONE
                else:
                    logger.error(f"Pipeline logic not yet implemented for state: {self.context.state}")
                    self.context.state = PipelineStatus.DONE
                await self.save_context()

            end_time = time.time()
            pipeline_duration = end_time - start_time
            self.context.pipeline_duration_seconds = int(pipeline_duration) 
            await self.save_context()
            logger.info(f"Pipeline completed in {pipeline_duration:.2f} seconds.")
        finally:
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
                                                process_config: ProcessConfig,
                                                current_data: int,
                                                required_data: int,
                                                minimum_required_data: int,
                                                ) -> PipelineStatus:
        """
        Calculate the next state for the pipeline based on the current progress and processed count.
        """
        request_id = self.context.request_id
        jurisdiction_id = self.context.jurisdiction_id

        current_total_cost = cost_utils.total_cost_by_request(request_id, jurisdiction_id)["total_cost"]
        logger.info(f"Current total cost for this run: ${current_total_cost:.2f}")

        cost_limit = process_config.pipeline_run_cost_limit
        if current_total_cost >= cost_limit:
            logger.error(f"Cost limit of ${cost_limit} reached. Current cost: ${current_total_cost:.2f}. Moving to next step.")
            return PipelineStatus.DONE

        has_target_role = self.context.progress.has_target_role
        has_target_divisions = self.context.progress.has_target_divisions

        if current_data >= minimum_required_data and has_target_role and has_target_divisions:
            logger.info("Enough data processed, moving to report generation...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_LLM

        max_pages_with_required_data = process_config.max_pages + required_data # Each person might have a profile page
        if processed_count >= max_pages_with_required_data:
            logger.info(f"Max pages ({max_pages_with_required_data}) reached, moving to next step...")
            return PipelineStatus.MERGE_RECORDS_WITHIN_LLM

        logger.info(f"Not enough data processed yet, collecting more data... {processed_count}/{max_pages_with_required_data}")
        return PipelineStatus.SCRAPE_PAGE
    
    def save_data(self, people: List[Person]):
        """
        Save the processed people data to a file as JSON.
        """ 
        jurisdiction_id = self.context.jurisdiction_id
        jurisdiction_type = id_utils.parse_jurisdiction_id(jurisdiction_id).jurisdiction_type

        serialized_people = [person.model_dump() for person in people]

        existing_data = data_path_utils.get_people(jurisdiction_id)
        existing_data[jurisdiction_type] = serialized_people

        people_file_path = data_path_utils.get_people_file_path(jurisdiction_id)

        # Ensure the directory exists
        if not os.path.exists(people_file_path):
            os.makedirs(os.path.dirname(people_file_path), exist_ok=True)

        with open(people_file_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4)