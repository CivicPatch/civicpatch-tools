# civpatch/lib/services/openai_test.rb
require "test_helper"
require "services/openai"
require "services/prompts/openai_prompts"

module Services
  class OpenaiPromptsTest < Minitest::Test
    def setup
      @openai = Openai.new
      @municipality_context = {
        state: "wa",
        municipality_entry: { "name" => "Spokane" },
        government_type: "mayor_council",

      }
      @content_file = File.join(__dir__, "..", "..", "fixtures", "spokane_markdown.md")
      @page_url = "https://testville.gov/council"

      @response = {
        "people" => [
          { "name" => "Jane Mayor", "positions" => ["Mayor"], "email" => "jane@testville.gov" },
        ]
      }

      @formatted_jane = { "name" => "Jane Mayor", "email" => "jane@testville.gov", "formatted" => true }
    end

    def test_prompt_output 
      # Assuming Openai has a method like `build_prompt` or similar
      prompt = @openai.extract_city_people(
        @municipality_context,
        @content_file,
        @page_url,
        @people_hint
      )
      puts "\nPROMPT OUTPUT:\n#{prompt}\n"
      refute_nil prompt
      assert_equal 7, prompt.length, "Expected 7 people to be extracted"
    end


  end
end
