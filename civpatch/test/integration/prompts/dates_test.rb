require "test_helper"
require "services/google_gemini/client"
require "services/openai"

module IntegrationTest
  module Prompts
    class DatesTest < Minitest::Test
      def setup
        google_gemini = Services::GoogleGemini::Client.new
        openai = Services::Openai.new
        @models = [google_gemini, openai]
        @municipality_context = {
          state: "wa",
          municipality_entry: { "name" => "Testville" },
          government_type: "mayor_council"
        }
        @page_url = "https://testville.gov/council"
        @people_hint = []
      end

      # When there are mulitple term dates for a person,
      # the prompt should pick the latter date
      # (ex: if a person has a term from 2010-2014 and another from a re-election,
      # in 2015-2019, the prompt should pick the 2015-2019 term)
      def test_dates_pick_latter_date
        input_file = File.join(__dir__, "..", "fixtures", "prompts", "multiple_dates", "input.md")
        expected_file = File.join(__dir__, "..", "fixtures", "prompts", "multiple_dates", "output.json")
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
          assert_equal expected.map { |p| p["start_dates"].map{ |d| d["data"] } }.sort,
                       result.map { |p| p["start_dates"].map{ |d| d["data"] } }.sort, "Model #{model.class.name} failed start date check"
          assert_equal expected.map { |p| p["end_dates"].map{ |d| d["data"] } }.sort,
                       result.map { |p| p["end_dates"].map{ |d| d["data"] } }.sort, "Model #{model.class.name} failed end date check"
        end
      end
    end
  end
end
