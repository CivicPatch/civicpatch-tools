import asyncio
import time
from typing import Dict, List, cast, Any

from schemas import (
    Link,
    LinkStatus,
    Person,
    PipelineContext,
    PipelineRequest,
    PipelineStatus,
    SearchLinksStep,
    PipelineConfig,
)
from shared.utils import config_utils, data_path_utils
from shared.schemas import ProcessConfig
from steps.step_00_prepare_pipeline.prepare_pipeline import prepare_pipeline
from steps.step_01_research_municipality.research_municipality import (
    research_municipality,
)
from steps.step_02_search_links.search_links import search_links
from steps.step_02_search_links.utils import SearchEngineNames
from steps.step_03_scrape_page.scrape_page import scrape_page
from steps.step_04_preprocess_page_content.preprocess_page_content import (
    preprocess_page_content,
)
# from steps.step_05_process_page_content.process_page_content import process_page_content
from steps.step_06_merge_records_within_llm.merge_records_within_llm import (
    merge_records_within_llm,
)
from steps.step_07_merge_records_across_llms.merge_records_across_llms import (
    merge_records_across_llms,
)
from steps.step_08_cleanup.cleanup import cleanup
from steps.step_09_maybe_send_to_github.maybe_send_to_github import maybe_send_to_github
from utils import cost_utils, log_utils
from pipelines.context_utils import load_or_create_context, save_context_to_file
from pipelines.config_utils import load_config_from_file, save_config_to_file
from pipelines.state import (
    get_next_link_with_status,
    get_link_status_by_url,
    handle_process_page_content_state
)

class Pipeline:
    def __init__(self, request_id: str, pipeline_request: PipelineRequest, remove_callback):
        self.context = load_or_create_context(request_id, pipeline_request)
        self.stop_requested = False
        self.remove_callback = remove_callback

    def set_state(self, new_state: PipelineStatus):
        self.context = self.context.model_copy(update={"state": new_state})

    def run(self):
        asyncio.run(self.run_async())

    # TODO: please simplify logic
    async def run_async(self, with_debug=False):
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
                    progress, result = research_municipality(self.context)
                    self.context.progress = progress 
                    self.context.research_municipality_step = result

                    if self.context.config.source_urls and len(self.context.config.source_urls) > 0:
                        logger.info("Source URLs provided, skipping link search.")
                        self.context.links = [
                            Link(url=sl, status=LinkStatus.PENDING.value)
                            for sl in self.context.config.source_urls
                        ]
                        self.context.state = PipelineStatus.SCRAPE_PAGE
                    else:
                        logger.info("Source URLs not found, using search engine for links.")
                        self.context.state = PipelineStatus.SEARCH_LINKS

                elif self.context.state == PipelineStatus.SEARCH_LINKS:
                    search_links_step = self.context.search_links_step
                    search_link_pointer = search_links_step.search_link_pointer

                    if search_link_pointer >= len(SearchEngineNames):
                        logger.info("All search engines have been processed.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                    else:
                        links, result = search_links(self.context)
                        self.context.links = links
                        self.context.search_links_step = result
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.SCRAPE_PAGE:
                    page_to_scrape = get_next_link_with_status(self.context.links, LinkStatus.PENDING)

                    if not page_to_scrape:
                        logger.info("No pending links left to scrape.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                        continue

                    result = await scrape_page(self.context, page_to_scrape)
                    self.context.links = result

                    link_status = get_link_status_by_url(self.context.links, page_to_scrape.url)
                    if link_status == LinkStatus.SCRAPED:
                        self.context.state = PipelineStatus.PREPROCESS_PAGE_CONTENT
                    else:
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.PREPROCESS_PAGE_CONTENT:
                    page_to_preprocess = get_next_link_with_status(self.context.links, LinkStatus.SCRAPED)
                    if not page_to_preprocess:
                        logger.info("No scraped links left to preprocess.")
                        self.context.state = PipelineStatus.MERGE_RECORDS_WITHIN_LLM
                        continue

                    links, result = preprocess_page_content(self.context, page_to_preprocess)
                    self.context.links = links
                    self.context.preprocess_page_content_step = result

                    link_status = get_link_status_by_url(self.context.links, page_to_preprocess.url)

                    if link_status == LinkStatus.PREPROCESSED:
                        self.context.state = PipelineStatus.PROCESS_PAGE_CONTENT
                    else:  # link_status == LinkStatus.PREPROCESSED_NO_CONTENT:
                        self.context.state = PipelineStatus.SCRAPE_PAGE

                elif self.context.state == PipelineStatus.PROCESS_PAGE_CONTENT:
                    current_cost = cost_utils.total_cost_by_request(
                        self.context.request_id, self.context.jurisdiction_id
                    )["total_cost"]
                    result, next_state = handle_process_page_content_state(
                        logger,
                        process_config,
                        self.context,
                        current_cost
                    )
                    
                    self.context.process_page_content_step = result
                    self.context.state = next_state

                elif self.context.state == PipelineStatus.MERGE_RECORDS_WITHIN_LLM:
                    result = merge_records_within_llm(self.context)
                    self.context.merge_records_within_llm_step = result
                    self.context.state = PipelineStatus.MERGE_RECORDS_ACROSS_LLMS

                elif self.context.state == PipelineStatus.MERGE_RECORDS_ACROSS_LLMS:
                    result = merge_records_across_llms(self.context)
                    self.save_data(result.people)
                    self.context.merge_records_across_llms_step = result
                    self.context.state = PipelineStatus.CLEANUP

                elif self.context.state == PipelineStatus.CLEANUP:
                    result = cleanup(self.context)
                    self.context.config.identities = result["identities"]
                    save_config_to_file(
                        self.context.jurisdiction_id,
                        self.context.config
                    )

                    self.context.state = PipelineStatus.MAYBE_SEND_TO_GITHUB

                elif self.context.state == PipelineStatus.MAYBE_SEND_TO_GITHUB:
                    end_time = time.time()
                    pipeline_duration = end_time - start_time
                    self.context.pipeline_duration = int(pipeline_duration)
                    logger.info(
                        f"Pipeline completed in {self.context.pipeline_duration} seconds."
                    )
                    cost_utils.log_costs(
                        self.context.request_id, self.context.jurisdiction_id
                    )
                    result = maybe_send_to_github(self.context)

                    self.context.state = PipelineStatus.DONE
                else:
                    logger.error(
                        f"Pipeline logic not yet implemented for state: {self.context.state}"
                    )
                    self.context.state = PipelineStatus.DONE
                await save_context_to_file(self.context)

        finally:
            self.cleanup()

            
    def cleanup(self):
        log_utils.cleanup_pipeline_logger(self.context.jurisdiction_id)
        if self.remove_callback:
            self.remove_callback(self.context.jurisdiction_id)

    def save_data(self, people: List[Person]):
        serialized_data = [person.model_dump() for person in people]
        data_path_utils.update_data_for_jurisdiction(
            self.context.jurisdiction_id, serialized_data
        )

    # TODO: def save_data_source()
