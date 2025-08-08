import os
import time
from markdownify import markdownify as md
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from steps.step_04_preprocess_page_content.filter_content import filter_content
import utils.data_path_utils as data_path_utils

def preprocess_page_content(context: PipelineContext, page_to_preprocess: Link):
    """
    Preprocess the scraped HTML content of a page.
    """
    print(f"Step 4: {PipelineStatus.PREPROCESS_PAGE_CONTENT.value}")

    time_start = time.time()

    cache_path = data_path_utils.get_cache_path(context["state"], context["geoid"])
    output_html_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "original.html")

    with open(output_html_file_path, "r", encoding="utf-8") as f:
        output_html = f.read()

    output_md = md(output_html)

    preprocessed_html  = filter_content(output_html)
    preprocessed_md = md(preprocessed_html)
    original_output_md_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "original.md")
    output_md_file_path = os.path.join(cache_path, page_to_preprocess["folder_name"], "preprocessed.md")
    
    with open(original_output_md_file_path, "w", encoding="utf-8") as f:
        f.write(output_md)

    with open(output_md_file_path, "w", encoding="utf-8") as f:
        f.write(preprocessed_md)

    # Update link status to 
    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_preprocess["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.PREPROCESSED.value})
        else:
            updated_links.append(link)
    
    time_end = time.time()
    elapsed_time = time_end - time_start
    total_elapsed_time_seconds = context["steps"][PipelineStatus.PREPROCESS_PAGE_CONTENT.value].get("total_elapsed_time_seconds", 0) + elapsed_time
    
    print(f"/Step 4: {PipelineStatus.PREPROCESS_PAGE_CONTENT.value} - Elapsed time: {elapsed_time:.2f} seconds.")

    return {
        "links": updated_links,
        "steps": {
            **context["steps"],
            PipelineStatus.PREPROCESS_PAGE_CONTENT.value: {
                "total_elapsed_time_seconds": total_elapsed_time_seconds,
            }
        }
    }
