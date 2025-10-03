import os
import time
from markdownify import markdownify as md
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from steps.step_04_preprocess_page_content.filter_content import filter_content
from utils import data_path_utils, log_utils

def preprocess_page_content(context: PipelineContext, page_to_preprocess: Link):
    """
    Preprocess the scraped HTML content of a page.
    """
    logger = log_utils.get_pipeline_logger(context["jurisdiction_id"])
    logger.info(f"Step 4: {PipelineStatus.PREPROCESS_PAGE_CONTENT.value}: {page_to_preprocess['url']}")
    jurisdiction_id = context["jurisdiction_id"]

    time_start = time.time()
    cache_path = data_path_utils.get_cache_path(jurisdiction_id)
    output_html_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "original.html")

    with open(output_html_file_path, "r", encoding="utf-8") as f:
        output_html = f.read()

    output_md = md(output_html)

    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]
    preprocessed_html  = filter_content(logger, output_html, government_type=government_type)
    preprocessed_md = md(preprocessed_html)

    preprocessed_html_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "preprocessed.html")
    original_output_md_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "original.md")
    output_md_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "preprocessed.md")

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

    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_preprocess["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": new_status})
        else:
            updated_links.append(link)
    
    time_end = time.time()
    elapsed_time = time_end - time_start
    total_elapsed_time_seconds = context["steps"][PipelineStatus.PREPROCESS_PAGE_CONTENT.value].get("total_elapsed_time_seconds", 0) + elapsed_time

    elapsed_times = context["steps"][PipelineStatus.PREPROCESS_PAGE_CONTENT.value].get("elapsed_times", [])
    elapsed_times.append(elapsed_time)

    average_elapsed_time_seconds = total_elapsed_time_seconds / len(elapsed_times) if elapsed_times else 0

    logger.info(f"/Step 4: {PipelineStatus.PREPROCESS_PAGE_CONTENT.value}\n")
    logger.info(f"-> Elapsed time: {elapsed_time:.2f} seconds")
    logger.info(f"-> Average elapsed time: {average_elapsed_time_seconds:.2f} seconds")
    logger.info(f"-> Total elapsed time: {total_elapsed_time_seconds:.2f} seconds")

    return {
        "links": updated_links,
        "steps": {
            **context["steps"],
            PipelineStatus.PREPROCESS_PAGE_CONTENT.value: {
                "elapsed_times": elapsed_times,
                "total_elapsed_time_seconds": total_elapsed_time_seconds,
                "average_elapsed_time_seconds": average_elapsed_time_seconds
            }
        }
    }
