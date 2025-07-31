from unittest.mock import patch
from bs4 import BeautifulSoup
from steps.step_02_preprocessing.content_filter import filter_relevant_nodes

#def test_process_node_with_relevant_content():
#  """
#  Test process_node with relevant content to ensure it identifies relevant nodes.
#  """
#  html = """
#  <html>
#    <body>
#      <p>Relevant content about council members.</p>
#    </body>
#  </html>
#  """
#  soup = BeautifulSoup(html, "html.parser")
#  node = soup.body
#
#  with patch("steps.step_02_preprocessing.entity_extraction.extract_data") as mock_extract_data:
#    mock_extract_data.return_value = (["John Doe"], [], [], [], [])
#    is_relevant = process_node(node)
#
#  assert is_relevant is True
#  assert len(node.find_all("p")) == 1  # Ensure the relevant content remains
#
#def test_process_node_with_irrelevant_content():
#  """
#  Test process_node with irrelevant content to ensure it removes irrelevant nodes.
#  """
#  html = """
#  <html>
#    <body>
#      <div class="irrelevant">This should be removed.</div>
#    </body>
#  </html>
#  """
#  soup = BeautifulSoup(html, "html.parser")
#  node = soup.body
#
#  with patch("steps.step_02_preprocessing.entity_extraction.extract_data") as mock_extract_data:
#    mock_extract_data.return_value = ([], [], [], [], [])
#    is_relevant = process_node(node)
#
#  assert is_relevant is False
#  assert len(node.find_all("div")) == 0  # Ensure irrelevant content is removed
#
#def test_process_node_with_images():
#  """
#  Test process_node to ensure it identifies relevant image nodes.
#  """
#  html = """
#  <html>
#    <body>
#      <img src="image.jpg" />
#      <img src="irrelevant.gif" />
#    </body>
#  </html>
#  """
#  soup = BeautifulSoup(html, "html.parser")
#  node = soup.body
#
#  with patch("steps.step_02_preprocessing.entity_extraction.extract_data") as mock_extract_data:
#    mock_extract_data.return_value = ([], [], [], [], [])
#    is_relevant = process_node(node)
#
#  assert is_relevant is True
#  assert len(node.find_all("img")) == 1  # Only whitelisted images should remain
#  assert node.find("img")["src"] == "image.jpg"

def test_filter_relevant_nodes_with_links():
  """
  Test relevant nodes to ensure it identifies relevant links.
  """
  html = """
  <html>
    <body>
      <a href="http://example.com">John Doe</a>
      <a href="http://irrelevant.com">Irrelevant</a>
    </body>
  </html>
  """
  soup = BeautifulSoup(html, "html.parser")
  node = soup.body

  with patch("steps.step_02_preprocessing.entity_extraction.extract_data") as mock_extract_data:
    mock_extract_data.side_effect = [
        (["John Doe"], [], [], [], []),  # Relevant link
        ([], [], [], [], []),  # Irrelevant node 
        ([], [], [], [], []),  # Irrelevant node
        ([], [], [], [], []),  # Irrelevant node
    ]
    is_relevant = filter_relevant_nodes(node)
    print(mock_extract_data.call_args_list)  # Debugging: Inspect calls to the mock

    assert is_relevant is True
    assert len(node.find_all("a")) == 1  # Only relevant links should remain
    assert node.find("a")["href"] == "http://example.com"