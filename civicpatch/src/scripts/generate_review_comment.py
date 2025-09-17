import json
import sys

def generate_review_comment(file_path):
    try:
        # Load the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Extract relevant information
        state = data.get("state", "Unknown")
        request_id = data.get("request_id", "Unknown")
        progress = data.get("progress", {})
        current_data = progress.get("current_data", 0)
        required_data = progress.get("required_data", 0)
        links = data.get("links", [])
        steps = data.get("steps", {})
        elected_officials = steps.get("RESEARCH_MUNICIPALITY", {}).get("elected_officials", [])
        
        # Start building the markdown
        markdown = []
        markdown.append(f"# Review for {state.upper()} Request ID: {request_id}")
        markdown.append("---")
        
        # Progress Section
        markdown.append("## Progress")
        markdown.append(f"- **Current Data**: {current_data}")
        markdown.append(f"- **Required Data**: {required_data}")
        if current_data < required_data:
            markdown.append("- **Status**: ❌ Insufficient data collected")
        else:
            markdown.append("- **Status**: ✅ Data collection complete")
        markdown.append("")
        
        # Links Section
        markdown.append("## Links")
        if links:
            for link in links:
                url = link.get("url", "Unknown URL")
                status = link.get("status", "Unknown Status")
                markdown.append(f"- [{url}]({url}) - Status: {status}")
        else:
            markdown.append("- **No links available**")
        markdown.append("")
        
        # Elected Officials Section
        markdown.append("## Elected Officials")
        if elected_officials:
            for official in elected_officials:
                name = official.get("name", "Unknown")
                roles = ", ".join(official.get("roles", []))
                markdown.append(f"- **{name}**: {roles}")
        else:
            markdown.append("- **No elected officials data available**")
        markdown.append("")
        
        # TODO: Add more sections as needed based on the JSON structure
        markdown.append("## TODO")
        markdown.append("- Add more detailed analysis if required")
        markdown.append("")
        
        # Combine markdown into a single string
        markdown_output = "\n".join(markdown)
        print(markdown_output)
    
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON file at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python generate_review_comment.py <file_path>")
    else:
        generate_review_comment(sys.argv[1])

if __name__ == "__main__":
    main()