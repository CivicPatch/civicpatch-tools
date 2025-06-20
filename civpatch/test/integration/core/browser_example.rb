require_relative "../../test_helper"

require "core/browser"

# Test URL
url = "https://redmond.gov/189"

# Options for the browser
options = {
  image_dir: "./tmp/images", # Directory to save images
  include_api_content: false
}

# Run the fetch_page_content method
result = Core::Browser.fetch_page_content(url, options)

# Save the result to a file for inspection
File.write("./tmp/final_output.html", result)

puts "Final HTML saved to ./tmp/final_output.html"
