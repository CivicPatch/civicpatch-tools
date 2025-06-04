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
    end

    def test_prompt_output 
      # Assuming Openai has a method like `build_prompt` or similar
      people = @openai.extract_city_people(
        @municipality_context,
        @content_file,
        @page_url,
        []
      )
      puts "\nPROMPT OUTPUT:\n#{people}\n"
      refute_nil people 
      assert_equal 7, people.length, "Expected 7 people to be extracted"
      assert_equal [[], ["District 1"], ["District 1"], ["District 2"], ["District 2"], ["District 3"], ["District 3"]], 
        people
          .map { |p| p["divisions"].map{ |d| d["data"]} }
    end

  end
end
