import json
import sys
from typing import List
from collections import defaultdict
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    WorkflowConfig,
    ResearchMunicipalityStep,
)
from domain.models import Official
from shared.utils import data_path_utils, config_utils
from pydantic import BaseModel
import utils.merge_utils as merge_utils

class ReviewDecision(BaseModel):
    comment: str
    approved: bool

def generate_review_comment(pipeline_context: PeopleCollectorContext, people: List[Official]) -> ReviewDecision:
    merge_step = pipeline_context.data.merge_records_across_llms_step

    agreement_score = merge_step.agreement_score
    disagreements_by_person = merge_step.disagreements
    validation_errors = merge_step.validation_errors
    missing_people = merge_step.missing_people

    all_sources = {source for person in people for source in person.source_urls}

    issues = generate_validation_errors(pipeline_context, people)
    has_validation_errors = len(validation_errors) > 0 or len(issues) > 0

    identity_errors = get_identity_mismatches(
        pipeline_context.data.research_municipality_step,
        pipeline_context.data.format_output_step.config    ,
        people,
    )
    identity_table = identities_mismatch_table(
        pipeline_context.data.research_municipality_step,
        pipeline_context.data.format_output_step.config,
        people,
    )
    # ----------------------------------------------

    markdown = []

    # Header section
    if has_validation_errors or identity_errors:
        markdown.append("# Rejected ❌")
        markdown.append("Rejected by Bot - please manually review.")
        markdown.append("### Issues\n")
        if missing_people:
            markdown.append("- Found missing people:")
            for person in missing_people:
                markdown.append(f"  - {person}")
            markdown.append("")
        for issue in issues:
            markdown.append(f"- {issue}")
        for err in identity_errors:
            markdown.append(f"- {err}")
        markdown.append("---\n")
    else:
        markdown.append("# Approved ✅")
        markdown.append("Approved by Bot.")

    markdown.append(f"\n## Agreement Score: {agreement_score:.2f}")
    markdown.append("\n---\n")

    # Data Sources section
    markdown.append("### Data Sources\n")
    for source in sorted(all_sources):
        markdown.append(f"- {source}")
    markdown.append("\n---\n")

    # Missing People section
    if missing_people:
        markdown.append("### Missing People\n")
        for person in missing_people:
            markdown.append(f"#### {person.name}")
            markdown.append(f"- Missing from: {', '.join(person.missing_from_llms)}")
            markdown.append(f"- Found in: {', '.join(person.found_in_llms)}")
            markdown.append("")
        markdown.append("---\n")

    markdown.append("### Identity Comparison\n")
    markdown.append(identity_table)
    markdown.append("\n---\n")

    # Disagreements section
    if disagreements_by_person:
        markdown.append("### Disagreements")
        for person_name, person_disagreements in disagreements_by_person.items():
            markdown.append(f"### {person_name}\n")
            markdown.append("| Field | Disagreement Score | gemini | openai | final_value |")
            markdown.append("| ----- | ------------------ | ------ | ------ | ----------- |")
            for disagreement in person_disagreements:
                field = disagreement.field
                score = disagreement.disagreement_score
                llm_values = disagreement.llm_values
                final_value = disagreement.merged_value or "_No consensus_"
                unique_values = set(llm_values.values())
                gemini_value = llm_values.get("google_gemini", "(missing)")
                openai_value = llm_values.get("openai", "(missing)")
                if len(unique_values) > 1:
                    gemini_value = f"**{gemini_value}**" if gemini_value != final_value else gemini_value
                    openai_value = f"**{openai_value}**" if openai_value != final_value else openai_value
                markdown.append(f"| {field} | {score:.2f} | {gemini_value} | {openai_value} | {final_value} |")
            markdown.append("\n---\n")

    return ReviewDecision(
        comment="\n".join(markdown),
        approved=not has_validation_errors and not identity_errors
    )

def generate_validation_errors(people_context: PeopleCollectorContext, people: List[Official]) -> List[str]:
    errors = []
    if not people:
        return ["No officials were found."]

    unique_roles = {r.lower() for r in config_utils.get_unique_roles()}
    designations_config = config_utils.get_designations()

    # Map unique role token -> list of person names
    role_to_persons = defaultdict(list)
    for person in people:
        office_tokens = [t.strip() for t in (person.office.name or "").lower().split(" - ") if t.strip()]
        for token in office_tokens:
            if token in unique_roles:
                role_to_persons[token].append(person.name)

    for role, persons in role_to_persons.items():
        if len(persons) > 1:
            errors.append(f"Role '{role}' is marked as unique, but found multiple persons with this role: {', '.join(persons)}")

    # Collect unique designations per person and invert to designation -> persons
    designation_to_persons = defaultdict(list)
    for person in people:
        designations = extract_unique_designations_from_office_name(person.office.name or "", designations_config)
        for d in designations:
            designation_to_persons[d].append(person.name)

    for designation, persons in designation_to_persons.items():
        if len(persons) > 1:
            errors.append(f"Designation '{designation}' is marked as unique, but found multiple persons with this designation: {', '.join(persons)}")

    return errors

def extract_unique_designations_from_office_name(office_name: str, designations_config: dict) -> List[str]:
    if not office_name:
        return []

    office_name_parts = [p.strip() for p in office_name.lower().split(" - ") if p.strip()]

    # Build a flat set of all aliases + canonical keys (lowercased) for unique designations
    alias_set = set()
    for key, cfg in designations_config.items():
        if cfg.get("is_unique"):
            aliases = [a.lower() for a in cfg.get("aliases", [])]
            alias_set.update(aliases)
            alias_set.add(key.lower())

    matches = []
    for part in office_name_parts:
        tokens = set(part.split())
        if tokens & alias_set:
            matches.append(part)

    return matches

def canonicalize_names(officials, identities):
    """Return a set of canonical names for a list of officials, using identities mapping and same_name comparison."""

    canonicals = set()
    for o in officials:
        name = o.name
        found = False
        if identities:
            for canonical, aliases in identities.items():
                if merge_utils.same_name(name, canonical):
                    canonicals.add(canonical)
                    found = True
                    break
                for alias in aliases:
                    if merge_utils.same_name(name, alias):
                        canonicals.add(canonical)
                        found = True
                        break
                if found:
                    break
        if not found:
            canonicals.add(name)
    return canonicals

def get_identity_mismatches(
    research_municipality: ResearchMunicipalityStep,
    config: WorkflowConfig, 
    people: list, 
) -> list:
    """Return a list of errors for canonical name mismatches."""
    identities = config.identities or {}
    research_canonicals = canonicalize_names(research_municipality.elected_officials, identities)
    people_canonicals = canonicalize_names(people, identities)

    errors = []
    extra_in_people = sorted(people_canonicals - research_canonicals)
    extra_in_research = sorted(research_canonicals - people_canonicals)

    for name in extra_in_people:
        errors.append(f"Extra official: {name}")
    for name in extra_in_research:
        errors.append(f"Missing official: {name}")

    return errors

def identities_mismatch_table(
    research_municipality: ResearchMunicipalityStep,
    config: WorkflowConfig, 
    people: list, 
) -> str:
    """
    Returns a markdown table comparing officials in research vs. final list,
    combining aliases under their canonical name using config.identities.
    """
    identities = config.identities or {}
    research_canonicals = canonicalize_names(research_municipality.elected_officials, identities)
    people_canonicals = canonicalize_names(people, identities)
    all_canonicals = sorted(research_canonicals | people_canonicals)

    table = [
        "| Canonical Name | In Research | In Data |",
        "|---------------|:-----------:|:-------:|"
    ]
    for name in all_canonicals:
        in_research = "✅" if name in research_canonicals else "❌"
        in_final = "✅" if name in people_canonicals else "❌"
        table.append(f"| {name} | {in_research} | {in_final} |")

    return "\n".join(table)

def load_pipeline_context_from_json(filepath: str) -> PeopleCollectorContext:
    with open(filepath, "r") as file:
        data = json.load(file)
        return PeopleCollectorContext(**data)

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_review_comment.py <jurisdiction_ocdid>")
        sys.exit(1)
    else:
        jurisdiction_ocdid = sys.argv[1]
        pipeline_context_file_path = data_path_utils.get_workflow_context_file_path(jurisdiction_ocdid)
        serialized_people = data_path_utils.get_data(jurisdiction_ocdid)
        people = [Official(**person) for person in serialized_people]

        pipeline_context = load_pipeline_context_from_json(pipeline_context_file_path)
        review_decision = generate_review_comment(pipeline_context, people)
        print(json.dumps(review_decision.model_dump()))
        

if __name__ == "__main__":
    main()