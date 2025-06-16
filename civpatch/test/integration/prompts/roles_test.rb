require "test_helper"
require "services/google_gemini/client"
require "services/openai"

module IntegrationTest
  module Prompts
    class RolesTest < Minitest::Test
      def setup
        google_gemini = Services::GoogleGemini::Client.new
        openai = Services::Openai.new
        @models = [google_gemini, openai]
        @municipality_context = {
          state: "wa",
          municipality_entry: { "name" => "Spokane" },
          government_type: "mayor_council"
        }
        @page_url = "https://testville.gov/council"
        @people_hint = []
      end
      def test_roles
        input_file = File.join(__dir__, "..", "fixtures", "prompts", "roles", "input.md")
        expected_file = File.join(__dir__, "..", "fixtures", "prompts", "roles", "output.json")
        expected = JSON.parse(File.read(expected_file))

        @models.each do |model|
          result = model.extract_city_people(
            @municipality_context,
            input_file,
            @page_url,
            @people_hint
          )

          assert_equal expected.length, result.length, "Expected #{expected.length} people to be extracted by #{model.class.name}"
          assert_equal expected.map { |p| p["name"] }.sort, result.map { |p| p["name"] }.sort, "Model #{model.class.name} failed name check"
          assert_equal expected.map { |p| p["roles"].map{ |d| d["data"] } }.sort,
                       result.map { |p| p["roles"].map{ |d| d["data"] } }.sort, "Model #{model.class.name} failed roles check"
          assert_equal expected.map { |p| p["divisions"].map{ |d| d["data"] } }.sort,
                       result.map { |p| p["divisions"].map{ |d| d["data"] } }.sort, "Model #{model.class.name} failed divisions check"
        end
      end
    end
  end
end
