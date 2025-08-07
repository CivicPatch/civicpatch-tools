from schemas import PipelineContext, Link, LinkStatus

def preprocess_page_content(context: PipelineContext, page_to_preprocess: Link):
    """
    Preprocess the scraped HTML content of a page.
    """
    print(f"Preprocessing page content for state: {context['state']}, GEOID: {context['geoid']}")

    # TODO: do work

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
