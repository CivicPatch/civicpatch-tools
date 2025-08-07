from schemas import PipelineContext, Link, LinkStatus

def process_page_content(context: PipelineContext, page_to_process: Link):
    """
    Process the preprocessed data to extract relevant information.
    """
    print("Processing data...")
    # Example: Print the data or perform some processing
    # This is a placeholder for actual processing logic

    # TODO: do work to actually call LLM, figure out if there's more data here...

    updated_progress = context["progress"]
    updated_progress["current_data"] += 1  # Increment the count of processed data

    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_process["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.DONE.value})
        else:
            updated_links.append(link)  
    return {
        "links": updated_links,
        "progress": updated_progress
    }