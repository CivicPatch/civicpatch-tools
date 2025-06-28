require "test_helper"
require "services/google_gemini/client"

module IntegrationTest
  class GoogleGeminiPromptsTest < Minitest::Test
    def setup
      @gemini = Services::GoogleGemini::Client.new
      @municipality_context = {
        state: "wa",
        municipality_entry: { "name" => "Spokane" },
        government_type: "mayor_council"
      }
      @page_url = "https://testville.gov/council"
      @people_hint = []
    end

    def test_research_municipality
      result = @gemini.research_municipality(@municipality_context)
      expected_file = File.join(__dir__, "..", "..", "fixtures", "prompts", "google_gemini",
                                "research_municipality", "output.json")
      expected = JSON.parse(File.read(expected_file))

      assert_equal expected["government_type"], result["government_type"]
      assert_equal expected["people"].map { |p| p["name"] }.sort,
                   result["people"].map { |p| p["name"] }.sort
    end

    def test_municipality_officials
      content_file = File.join(__dir__, "..", "fixtures", "spokane_markdown.md")
      result = @gemini.extract_city_people(
        @municipality_context,
        content_file,
        @page_url,
        @people_hint
      )

      expected_file = File.join(__dir__, "..", "..", "fixtures", "prompts", "google_gemini",
                                "municipality_officials", "output.json")
      expected = JSON.parse(File.read(expected_file))

      assert_equal expected.length, result.length, "Expected #{expected.length} people to be extracted"
      assert_equal expected.map { |p| p["name"] }.sort, result.map { |p| p["name"] }.sort
      assert_equal expected.map { |p| p["roles"].map{ |role_data| role_data["data"] } }.sort, 
                     result.map { |p| p["roles"].map{ |role_data| role_data["data"] } }.sort
      assert_equal expected.map { |p| p["divisions"].map{ |division_data| division_data["data"] } }.sort, 
                     result.map { |p| p["divisions"].map{ |division_data| division_data["data"] } }.sort
    end

    def test_divisions
      content_file = File.join(TEST_DIR, "integration", "fixtures", "prompts", "google_gemini", "divisions_input.md")

      municipality_context = {
        state: "co",
        municipality_entry: { "name" => "Greeley" },
        government_type: "mayor_council"
      }
      
      result = @gemini.extract_city_people(
        municipality_context,
        content_file,
        @page_url,
        @people_hint
      )

      File.write("tmp/output.json", JSON.pretty_generate(result))
      
      assert_equal 5, result.length, "Expected  divisions to be extracted"
    end
  end
end
