import os
from fastapi.testclient import TestClient
from civicpatch.src.main import app
from markdownify import markdownify as md

client = TestClient(app)

# def test_extract_with_relevant_data():
#     input_data = {
#         "text": """
#         <html>
#             <body>
#                 <p>John Doe is the mayor of Springfield. Contact him at john.doe@example.com or (555) 123-4567.</p>
#                 <p>Visit his website at https://johndoe.com.</p>
#             </body>
#         </html>
#         """
#     }
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert "John Doe" in data["people"]
#     assert "mayor" in data["roles"]
#     assert "john.doe@example.com" in data["emails"]
#     assert "(555) 123-4567" in data["phones"]
#     assert "https://johndoe.com" in data["websites"]
# 
# def test_extract_with_irrelevant_data():
#     input_data = {
#         "text": """
#         <html>
#             <body>
#                 <p>This is some random text with no relevant information.</p>
#             </body>
#         </html>
#         """
#     }
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["people"] == []
#     assert data["roles"] == []
#     assert data["emails"] == []
#     assert data["phones"] == []
#     assert data["websites"] == []
# 
# def test_extract_with_mixed_data():
#     input_data = {
#         "text": """
#         <html>
#             <body>
#                 <p>Jane Smith is a council member. Contact her at jane.smith@example.com.</p>
#                 <p>This is irrelevant text.</p>
#             </body>
#         </html>
#         """
#     }
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert "Jane Smith" in data["people"]
#     assert "council member" in data["roles"]
#     assert "jane.smith@example.com" in data["emails"]
#     assert data["phones"] == []
#     assert data["websites"] == []
# 
# def test_extract_with_empty_input():
#     input_data = {"text": ""}
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert data["people"] == []
#     assert data["roles"] == []
#     assert data["emails"] == []
#     assert data["phones"] == []
#     assert data["websites"] == []
#     assert data["filtered_html"] == ""
# 
# def test_extract_with_nested_html():
#     input_data = {
#         "text": """
#         <html>
#             <body>
#                 <div>
#                     <p>Emily Johnson is a representative. Contact her at emily.johnson@example.com.</p>
#                 </div>
#                 <div>
#                     <p>Random text here.</p>
#                 </div>
#             </body>
#         </html>
#         """
#     }
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
#     data = response.json()
#     assert "Emily Johnson" in data["people"]
#     assert "representative" in data["roles"]
#     assert "emily.johnson@example.com" in data["emails"]
#     assert data["phones"] == []
#     assert data["websites"] == []

#def test_extract_with_camas_mayor_fixture():
#    # Define the paths to the fixture files
#    base_path = os.path.dirname(__file__)
#    input_file = os.path.join(base_path, "./fixtures/camas_mayor.html")
#    expected_file = os.path.join(base_path, "./fixtures/camas_mayor_expected.md")
# 
#    # Read the input HTML
#    with open(input_file, "r") as f:
#        input_html = f.read()
# 
#    # Prepare the input data for the API
#    input_data = {"text": input_html}
# 
#    # Make the API request
#    response = client.post("/extract", json=input_data)
#    assert response.status_code == 200
# 
#    # Get the filtered HTML from the response
#    data = response.json()
#    filtered_content = data["filtered_content"].strip()
# 
#    # Check if the expected file exists
#    if not os.path.exists(expected_file):
#        # If the expected file doesn't exist, write the filtered HTML to it
#        with open(expected_file, "w") as f:
#            f.write(filtered_content)
#        # Fail the test to indicate that the expected file was created
#        assert False, f"Expected file did not exist. Generated at: {expected_file}"
# 
#    # Read the expected filtered content
#    with open(expected_file, "r") as f:
#        expected_content = f.read().strip()
# 
#    # Compare the filtered content to the expected content
#    assert filtered_content == expected_content
# 
# def test_extract_with_camas_noinfo_fixture():
#     # Define the paths to the fixture files
#     base_path = os.path.dirname(__file__)
#     input_file = os.path.join(base_path, "./fixtures/camas_noinfo.html")
#     expected_file = os.path.join(base_path, "./fixtures/camas_noinfo_expected.md")
# 
#     # Read the input HTML
#     with open(input_file, "r") as f:
#         input_html = f.read()
# 
#     # Prepare the input data for the API
#     input_data = {"text": input_html}
# 
#     # Make the API request
#     response = client.post("/extract", json=input_data)
#     assert response.status_code == 200
# 
#     # Get the filtered HTML from the response
#     data = response.json()
#     filtered_content = data["filtered_content"].strip()
# 
#     # Check if the expected file exists
#     if not os.path.exists(expected_file):
#         # If the expected file doesn't exist, write the filtered HTML to it
#         with open(expected_file, "w") as f:
#             f.write(filtered_content)
#         # Fail the test to indicate that the expected file was created
#         assert False, f"Expected file did not exist. Generated at: {expected_file}"
# 
#     # Read the expected filtered HTML
#     with open(expected_file, "r") as f:
#         expected_content = f.read().strip()
# 
#     # Compare the filtered HTML to the expected HTML
#     assert filtered_content == expected_content
# 
#     print(data["people"])
# 
#     assert data["people"] == []
#     assert data["roles"] == []
#     assert data["dates"] == []
#     assert data["emails"] == []
#     assert data["phones"] == []
#     assert data["websites"] == []

def test_extract_with_yakima_council_fixture():
    # Define the paths to the fixture files
    base_path = os.path.dirname(__file__)
    input_file = os.path.join(base_path, "./fixtures/yakima_council.html")
    original_input_file_md = os.path.join(base_path, "./fixtures/yakima_council_original.md")

    expected_file = os.path.join(base_path, "./fixtures/yakima_council_expected.md")

    # Read the input HTML
    with open(input_file, "r") as f:
      input_html = f.read()
   
    # Save original file as markdown
    with open(original_input_file_md, "w") as f:
      f.write(md(input_html))

    # Prepare the input data for the API
    input_data = {"text": input_html}

    # Make the API request
    response = client.post("/extract", json=input_data)
    assert response.status_code == 200

    # Get the filtered HTML from the response
    data = response.json()
    filtered_content = data["filtered_content"].strip()

    # Check if the expected file exists
    if not os.path.exists(expected_file):
        os.makedirs(os.path.dirname(expected_file), exist_ok=True)
        with open(expected_file, "w") as f:
            f.write(filtered_content)
        print("File written:", expected_file)
        assert False, f"Expected file did not exist. Generated at: {expected_file}"

    # Read the expected filtered HTML
    with open(expected_file, "r") as f:
      expected_content = f.read().strip()

    # Compare the filtered HTML to the expected HTML
    assert filtered_content == expected_content

    print(data["people"])