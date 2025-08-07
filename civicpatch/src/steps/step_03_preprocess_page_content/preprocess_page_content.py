import os
from markdownify import markdownify as md
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from steps.step_03_preprocess_page_content.filter_content import filter_content
import utils.data_path_utils as data_path_utils

def preprocess_page_content(context: PipelineContext, page_to_preprocess: Link):
    """
    Preprocess the scraped HTML content of a page.
    """
    print(f"Step 3: {PipelineStatus.PREPROCESS_PAGE_CONTENT.value}")

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

    return {
        "links": updated_links,
    }
