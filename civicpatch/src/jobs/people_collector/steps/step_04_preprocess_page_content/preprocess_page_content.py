import os
import time
from markdownify import markdownify as md
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    Link, 
    LinkStatus, 
    WorkflowStatus, 
    PreprocessPageContentStep, 
    ResearchMunicipalityStep
)
from shared.utils import data_path_utils
from jobs.people_collector.steps.step_04_preprocess_page_content.filter_content import filter_content
from utils import log_utils
from typing import List

DEFAULT_PREPROCESS_PAGE_CONTENT_STEP = PreprocessPageContentStep(
    elapsed_times=[],
    total_elapsed_time_seconds=0,
    average_elapsed_time_seconds=0
)

def preprocess_page_content(
    context: PeopleCollectorContext, page_to_preprocess: Link
    ) -> tuple[List[Link], PreprocessPageContentStep]:
    """
    Preprocess the scraped HTML content of a page.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 4: {WorkflowStatus.PREPROCESS_PAGE_CONTENT.value}: {page_to_preprocess.url}")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    time_start = time.time()
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    output_html_file_path = os.path.join(cache_path, page_to_preprocess.folder_name, "original.html")

    with open(output_html_file_path, "r", encoding="utf-8") as f:
        output_html = f.read()

    output_md = md(output_html, keep_inline_images_in=['td', 'th'])

    government_type = context.data.research_municipality_step.government_type
    research_elected_officials = getattr(
        context.data.research_municipality_step, "elected_officials", {}
    )
    research_identities = {official.name: [official.name] for official in research_elected_officials}
    runtime_identities = getattr(
        context.data.process_page_content_step, "identities", {}
    )
    identities = context.data.config.identities or runtime_identities or research_identities
    logger.debug(f"-> Preprocessing with identities: {identities}")
    preprocessed_html  = filter_content(logger, identities, output_html, government_type=government_type)
    preprocessed_md = md(preprocessed_html, keep_inline_images_in=['td', 'th'])

    preprocessed_html_file_path = os.path.join(cache_path, page_to_preprocess.folder_name, "preprocessed.html")
    original_output_md_file_path = os.path.join(cache_path, page_to_preprocess.folder_name, "original.md")
    output_md_file_path = os.path.join(cache_path, page_to_preprocess.folder_name, "preprocessed.md")

    with open(preprocessed_html_file_path, "w", encoding="utf-8") as f:
        f.write(preprocessed_html)
    
    with open(original_output_md_file_path, "w", encoding="utf-8") as f:
        f.write(output_md)

    with open(output_md_file_path, "w", encoding="utf-8") as f:
        f.write(preprocessed_md)

    # Update link status to PREPROCESSED or PREPROCESSED_NO_CONTENT
    if preprocessed_md.strip():
        new_status = LinkStatus.PREPROCESSED.value
    else:
        new_status = LinkStatus.PREPROCESSED_NO_CONTENT.value

    updated_links: List[Link] = []
    for link in context.data.links:
        if link.url == page_to_preprocess.url:
            # Update the status/content for this link
            link.status = new_status
            updated_links.append(link)
        else:
            updated_links.append(link)
    
    time_end = time.time()
    elapsed_time = time_end - time_start

    preprocess_page_content_step = context.data.preprocess_page_content_step
    if preprocess_page_content_step is None:
        preprocess_page_content_step = DEFAULT_PREPROCESS_PAGE_CONTENT_STEP

    total_elapsed_time_seconds = preprocess_page_content_step.total_elapsed_time_seconds + elapsed_time

    elapsed_times = preprocess_page_content_step.elapsed_times
    elapsed_times.append(int(elapsed_time))

    average_elapsed_time_seconds = total_elapsed_time_seconds / len(elapsed_times) if elapsed_times else 0

    logger.info(f"/Step 4: {WorkflowStatus.PREPROCESS_PAGE_CONTENT.value}\n")
    logger.info(f"-> Elapsed time: {elapsed_time:.2f} seconds")
    logger.info(f"-> Average elapsed time: {average_elapsed_time_seconds:.2f} seconds")
    logger.info(f"-> Total elapsed time: {total_elapsed_time_seconds:.2f} seconds")

    return updated_links, PreprocessPageContentStep(
        elapsed_times=elapsed_times,
        total_elapsed_time_seconds=int(total_elapsed_time_seconds),
        average_elapsed_time_seconds=int(average_elapsed_time_seconds)
    )
