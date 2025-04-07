require "test_helper"
require_relative "../../lib/validators/utils"

module Validators
  class UtilsTest < Minitest::Test
    DISAGREEMENT_THRESHOLD = 0.9

    def setup
      @source_confidences = [0.9, 0.7, 0.7]
      @source1 = [
        { "name" => "Alice Smith", "positions" => ["Mayor"] },
        { "name" => "Bob Jones", "positions" => ["Council Member"], "email" => "bob.jones@example.com",
          "phone_number" => "555-123-4567", "website" => "bob.com" }
      ]

      @source2 = [
        { "name" => "Alice Smith", "positions" => ["Mayor"], "email" => "alice.smith@example.com",
          "phone_number" => "1234567890", "website" => "alice.com" },
        { "name" => "Bob Jones", "positions" => ["Councilman"], "email" => "bob.jones@example.com",
          "phone_number" => "555-123-4567", "website" => "bob-jones.com" }
      ]

      @source3 = [
        { "name" => "Alice Smith", "positions" => ["Mayor"], "email" => "alice.smith@example.com",
          "phone_number" => "123-456-7890", "website" => "alice.org" },
        { "name" => "Bob Jones", "positions" => ["Council Member"], "email" => "bob.jones@example.com",
          "phone_number" => "555-123-4567", "website" => "bob.com" }
      ]
    end

    ### TESTING SIMILARITY SCORE ###
    def test_similarity_exact_match
      assert_equal 1.0, Validators::Utils.similarity_score("phone_number", "123-456-7890", "123-456-7890")
      assert_equal 1.0, Validators::Utils.similarity_score("email", "alice@example.com", "alice@example.com")
    end

    def test_similarity_phone_normalization
      assert_equal 1.0, Validators::Utils.similarity_score("phone_number", "123-456-7890", "1234567890")
      assert_equal 0.0, Validators::Utils.similarity_score("phone_number", "123-456-7890", "987-654-3210")
    end

    def test_similarity_email_gmail_normalization
      assert_in_delta 1.0, Validators::Utils.similarity_score("email", "alice.smith@gmail.com", "alicesmith@gmail.com"),
                      0.1
      assert_equal 0.0, Validators::Utils.similarity_score("email", "alice@example.com", "bob@example.com")
    end

    def test_similarity_levenshtein
      assert_in_delta 0.8, Validators::Utils.similarity_score("positions", ["Council Member"], ["Councilman"]), 0.2
      assert_equal 0.25, Validators::Utils.similarity_score("positions", ["Mayor"], ["Council Member"])
      assert_equal 0.625,
                   Validators::Utils.similarity_score("positions", ["Mayor", "Council Member"], ["Council Member"])
    end

    ### TESTING DATA AGREEMENT ###
    def test_compare_people_across_sources
      result = Validators::Utils.compare_people_across_sources(
        [@source1, @source2, @source3], @source_confidences
      )

      expected_contested_people = {
        "Alice Smith" => {
          "website" => {
            disagreement_score: 0.5333333333333333,
            values: [nil, "alice.com", "alice.org"]
          }
        },
        "Bob Jones" => {
          "positions" => {
            disagreement_score: 0.5039216291753892,
            values: [["Council Member"], ["Councilman"], ["Council Member"]]
          },
          "website" => {
            disagreement_score: 0.5726094035972584,
            values: ["bob.com", "bob-jones.com", "bob.com"]
          }
        }
      }

      assert_equal expected_contested_people, result[:contested_people]
    end

    def test_compare_people_across_sources_with_positions
      result = Validators::Utils.compare_people_across_sources(
        [@source1, @source2, @source3], @source_confidences
      )

      expected_contested_people = {
        "Alice Smith" => {
          "website" => {
            disagreement_score: 0.5333333333333333,
            values: [nil, "alice.com", "alice.org"]
          }
        },
        "Bob Jones" => {
          "positions" => {
            disagreement_score: 0.5039216291753892,
            values: [["Council Member"], ["Councilman"], ["Council Member"]]
          },
          "website" => {
            disagreement_score: 0.5726094035972584,
            values: ["bob.com", "bob-jones.com", "bob.com"]
          }
        }
      }

      assert_equal expected_contested_people, result[:contested_people]
    end

    def test_similarity_exact_match_for_positions
      value1 = ["Council Member"]
      value2 = ["Council Member"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      assert_equal 1.0, similarity
    end

    def test_similarity_slight_difference_in_positions
      value1 = ["Council Member"]
      value2 = ["Councilman"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # Assuming some acceptable range for slight differences
      assert_in_delta 0.8, similarity, 0.2
    end

    def test_similarity_larger_difference_in_positions
      value1 = ["Mayor"]
      value2 = ["Council Member"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # The larger the difference, the lower the similarity
      assert_in_delta 0.25, similarity, 0.2
    end

    def test_similarity_multiple_positions_comparison
      value1 = ["Council Member", "Councilman"]
      value2 = ["Councilman", "Council Member"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # Check that average similarity is calculated for multiple positions
      assert_in_delta 0.8, similarity, 0.2
    end

    def test_similarity_with_nil_value
      value1 = ["Council Member"]
      value2 = nil
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      assert_equal 0.5, similarity
    end

    def test_similarity_with_mixed_nil_values
      value1 = ["Council Member"]
      value2 = []
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # Similarity should not be penalized when one value is nil
      assert_equal 0.5, similarity
    end
  end
end
