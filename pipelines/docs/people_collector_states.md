## people_collector state transitions

Keep this diagram in sync with `transitions/main.py` whenever states or edges change.

```mermaid
stateDiagram-v2
    state all_scrapes_failed <<choice>>
    state no_content_found <<choice>>
    state no_officials_found <<choice>>

    [*] --> INIT

    INIT --> RESEARCH_MUNICIPALITY

    RESEARCH_MUNICIPALITY --> SCRAPE_PAGE : source_urls provided
    RESEARCH_MUNICIPALITY --> SEARCH_LINKS : no source_urls

    SEARCH_LINKS --> SEARCH_LINKS : no links found (try next engine)
    SEARCH_LINKS --> SCRAPE_PAGE : links found / all engines exhausted

    SCRAPE_PAGE --> PREPROCESS_PAGE_CONTENT : page scraped
    SCRAPE_PAGE --> SCRAPE_PAGE : scrape failed, more pending links
    SCRAPE_PAGE --> all_scrapes_failed : no pending links, all links ERROR
    SCRAPE_PAGE --> MERGE_RECORDS_WITHIN_LLM : no pending links, some pages scraped

    all_scrapes_failed --> FIND_JURISDICTION_URL : url_recovery_attempted = false
    all_scrapes_failed --> SEND_ERROR : url_recovery_attempted = true (DOMAIN_INACTIVE)

    PREPROCESS_PAGE_CONTENT --> PROCESS_PAGE_CONTENT : link has content
    PREPROCESS_PAGE_CONTENT --> SCRAPE_PAGE : link has no content
    PREPROCESS_PAGE_CONTENT --> no_content_found : no scraped or preprocessed links
    PREPROCESS_PAGE_CONTENT --> PROCESS_PAGE_CONTENT : no scraped links, preprocessed links exist

    no_content_found --> FIND_JURISDICTION_URL : url_recovery_attempted = false
    no_content_found --> SEND_ERROR : url_recovery_attempted = true (DOMAIN_INACTIVE)

    PROCESS_PAGE_CONTENT --> SCRAPE_PAGE : more pages needed
    PROCESS_PAGE_CONTENT --> MERGE_RECORDS_WITHIN_LLM : enough data collected
    PROCESS_PAGE_CONTENT --> MERGE_RECORDS_ACROSS_LLMS : no preprocessed links (not all error)
    PROCESS_PAGE_CONTENT --> SEND_ERROR : all pages error / cost or page limit exceeded

    MERGE_RECORDS_WITHIN_LLM --> MERGE_RECORDS_ACROSS_LLMS

    MERGE_RECORDS_ACROSS_LLMS --> FORMAT_OUTPUT

    FORMAT_OUTPUT --> CLEANUP

    CLEANUP --> REVIEW_OUTPUT

    REVIEW_OUTPUT --> no_officials_found : no officials found
    REVIEW_OUTPUT --> SEND_ERROR : heuristics fail (NO_INFO, etc.)
    REVIEW_OUTPUT --> SAVE_OUTPUT : officials found and valid

    no_officials_found --> FIND_JURISDICTION_URL : url_recovery_attempted = false
    no_officials_found --> SEND_ERROR : url_recovery_attempted = true (NO_INFO)

    FIND_JURISDICTION_URL --> SEND_ERROR : no URL discovered (DOMAIN_INACTIVE)
    FIND_JURISDICTION_URL --> REVIEW_OUTPUT : discovered URL same as current
    FIND_JURISDICTION_URL --> SCRAPE_PAGE : new URL discovered

    SAVE_OUTPUT --> SEND_SUCCESS

    SEND_SUCCESS --> [*]
    SEND_ERROR --> [*]
```
