import argparse
from utils.pipeline_utils import get_municipalities_to_scrape
from pipeline import Pipeline, PipelineStatus


def main():
    parser = argparse.ArgumentParser(description="CivicPatch CLI")
    parser.add_argument("action", choices=["search", "pipeline", "github"], help="Action to perform")
    parser.add_argument("--state", type=str, required=True, help="State to process")
    parser.add_argument("--num", type=int, default=0, help="GEOIDs to find")
    parser.add_argument("--geoid", type=str, default=None, help="Municipality GEOID to process")
    parser.add_argument("--geoids-to-ignore", type=str, nargs='*', default=None, help="List of GEOIDs to ignore")
    
    args = parser.parse_args()

    if args.action == "search":
        geoids = get_municipalities_to_scrape(args.state, args.num, args.geoids_to_ignore)
        if len(geoids) == 0:
            print(f"No municipalities found for state {args.state} with the specified criteria.")
            return
        print(geoids)
    elif args.action == "pipeline":
        pipeline = Pipeline(pipeline_state=PipelineStatus.INIT)
        pipeline.run(args.state, args.geoid)

    #elif args.action == "github":
    #    print(f"Triggered GitHub steps for state: {args.state}, geoid: {args.geoid}")
    else:
        print("Invalid action specified. Use 'search' or 'github'.")

if __name__ == "__main__":
    main()

#import time
#from fastapi import FastAPI
#from pydantic import BaseModel
#import spacy, re
#from bs4 import BeautifulSoup, Tag
#from spacy.matcher import PhraseMatcher
#from markdownify import markdownify as md

# IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]
# def extract(input: Input):
#     start_time = time.time()
#     # Parse the input text as HTML
#     soup = BeautifulSoup(input.text, "html.parser")
#     people = []
#     roles = []
#     dates = []
#     emails = []
#     phones = []
#     websites = []
#     images = []
#     
#     # Process all top-level nodes
#     nodes_to_remove = []
#     for node in soup.find_all(True, recursive=False):
#         if not prlevant:
#             people.extend(found_people)
#             roles.extend(found_roles)
#             dates.extend(found_dates)
#             emails.extend(found_emails)
#             phones.extend(found_phones)
#             websites.extend(found_websites)
#             images.extend(ocess_node(node):
#             nodes_to_remove.append(node)
#     
#     # Remove irrelevant top-level nodes
#     for node in nodes_to_remove:
#         node.decompose()
# 
#     # Deduplicate the lists while preserving order
#     people = list(dict.fromkeys(people))
#     roles = list(dict.fromkeys(roles))
#     dates = list(dict.fromkeys(dates))
#     emails = list(dict.fromkeys(emails))
#     phones = list(dict.fromkeys(phones))
#     websites = list(dict.fromkeys(websites))
#     images = list(dict.fromkeys(images))
# 
#     # Return an object with the filtered HTML and extracted data
#     end_time = time.time()
#     print("People found:", people, "in: ", end_time - start_time, "seconds")
#     print("Roles found:", roles)
#     print("Dates found:", dates)
#     print("Emails found:", emails)
#     print("Phones found:", phones)
#     print("Websites found:", websites)
#     print("Images found:", images)
#     return {
#         "filtered_content": md(soup.prettify()),
#         "people": people,
#         "roles": roles,
#         "dates": dates,
#         "emails": emails,
#         "phones": phones,
#         "websites": websites,
#         "images": images,
#         "processing_time_s": (end_time - start_time)
#     }