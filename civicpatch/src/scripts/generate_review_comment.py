import os
import json
import yaml
import sys
from collections import Counter
from typing import List
from schemas import PipelineContext, Person, MergeRecordsAcrossLLMsStep

def generate_review_comment(pipeline_context: PipelineContext, people: List[Person]) -> str:
    # Get data from MERGE_RECORDS_ACROSS_LLMS step
    merge_step: MergeRecordsAcrossLLMsStep = pipeline_context.steps.get("MERGE_RECORDS_ACROSS_LLMS", {})
    agreement_score = merge_step.agreement_score
    disagreements_by_person = merge_step.disagreements  # Now a Dict[str, List[FieldComparison]]
    validation_issues = merge_step.validation_issues
    missing_people = merge_step.missing_people

    # Collect all unique data sources from people.yml
    all_sources = {source for person in people for source in person.sources}

    has_validation_issues = len(validation_issues) > 0

    # Build the markdown
    markdown = []
    
    # Header section
    if has_validation_issues:
        markdown.append("# Rejected ❌")
        markdown.append("Rejected by Bot - please manually review.")
        markdown.append("### Issues\n")
        if missing_people:
            markdown.append("- Found missing people:")
            for person in missing_people:
                markdown.append(f"  - {person}")
            markdown.append("")

        # Add any other validation issues here
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

    # Disagreements section
    if disagreements_by_person:
        markdown.append("### Disagreements")
        for person_name, person_disagreements in disagreements_by_person.items():
            markdown.append(f"### {person_name}\n")
            
            markdown.append("| Field | Disagreement Score | gemini | openai | together_ai | final_value |")
            markdown.append("| ----- | ------------------ | ------ | ------ | ----------- | ----------- |")

            for disagreement in person_disagreements:
                field = disagreement.field
                score = disagreement.disagreement_score
                llm_values = disagreement.llm_values
                final_value = disagreement.merged_value or "_No consensus_"
                
                # Get all unique values to determine which ones differ
                unique_values = set(llm_values.values())
                
                # If a value is unique (doesn't match others), it should be bold
                gemini_value = llm_values.get("google_gemini", "")
                openai_value = llm_values.get("openai", "")
                together_value = llm_values.get("together_ai", "")
                
                # Bold values that don't match the final value
                if len(unique_values) > 1:
                    gemini_value = f"**{gemini_value}**" if gemini_value != final_value else gemini_value
                    openai_value = f"**{openai_value}**" if openai_value != final_value else openai_value
                    together_value = f"**{together_value}**" if together_value != final_value else together_value

                markdown.append(f"| {field} | {score:.2f} | {gemini_value} | {openai_value} | {together_value} | {final_value} |")
            
            markdown.append("\n---\n")

    return "\n".join(markdown)

def load_people_from_yaml(filepath: str) -> List[Person]:
    """
    Load a list of Person objects from a YAML file.
    """
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        return [Person(**person_data) for person_data in data]

def load_pipeline_context_from_json(filepath: str) -> PipelineContext:
    """
    Load a PipelineContext object from a JSON file.
    """
    with open(filepath, "r") as file:
        data = json.load(file)
        return PipelineContext(**data)

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_review_comment.py <file_path>")
        sys.exit(1)
    else:
        municipality_path = sys.argv[1]
        # It should be defined in the dockerfile
        PYTHONPATH = os.getenv("PYTHONPATH", "/app/src")
        pipeline_context_file_path = os.path.join(PYTHONPATH, "..", "data_source", municipality_path, "pipeline_context.json")
        people_file_path = os.path.join(PYTHONPATH, "..", "data", municipality_path, "people.yml")

        pipeline_context = load_pipeline_context_from_json(pipeline_context_file_path)
        people = load_people_from_yaml(people_file_path)
        comment = generate_review_comment(pipeline_context, people)
        print(comment)

if __name__ == "__main__":
    main()