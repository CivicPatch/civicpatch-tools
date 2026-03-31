# Quirks

## Human Review - scrapeable once url is known
- https://www.grandsalinetx.gov/page/city-council
    This results in a failed pipeline, because if you look at the HTML
    the only reference to city-council you can see is the city-council slug.
    Have to resolve it by either search engine (Google LLM API) or just have a human review it