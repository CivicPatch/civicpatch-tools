require "test_helper"
require_relative "../../lib/validators/utils"

module Validators
  class UtilsTest < Minitest::Test
    DISAGREEMENT_THRESHOLD = 0.9

    def setup
      @source_confidences = [0.9, 0.7, 0.7]
      @source1 = {
        confidence_score: 0.9,
        source_name: "source1",
        people: [
          { "name" => "Alice Smith", "positions" => ["Mayor"] },
          { "name" => "Bob Jones", "positions" => ["Council Member"], "email" => "bob.jones@example.com",
            "phone_number" => "555-123-4567", "website" => "bob.com" }
        ]
      }

      @source2 = {
        confidence_score: 0.8,
        source_name: "source2",
        people: [
          { "name" => "Alice Smith", "positions" => ["Mayor"], "email" => "alice.smith@example.com",
            "phone_number" => "1234567890", "website" => "alice.com" },
          { "name" => "Bob Jones", "positions" => ["Councilman"], "email" => "bob.jones@example.com",
            "phone_number" => "555-123-4567", "website" => "bob-jones.com" }
        ]
      }

      @source3 = {
        confidence_score: 0.8,
        source_name: "source3",
        people: [
          { "name" => "Alice Smith", "positions" => ["Mayor"], "email" => "alice.smith@example.com",
            "phone_number" => "123-456-7890", "website" => "alice.org" },
          { "name" => "Bob Jones", "positions" => ["Council Member"], "email" => "bob.jones@example.com",
            "phone_number" => "555-123-4567", "website" => "bob.com" }
        ]
      }

      @sources = [@source1, @source2, @source3]

      @contested_people = {
        "Bob Jones" => {
          "positions" => { disagreement_score: 0.7 },
          "website" => { disagreement_score: 0.6 }
        },
        "Alice Smith" => {
          "email" => { disagreement_score: 0.1 },
          "website" => { disagreement_score: 0.8 }
        }
      }
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
      assert_in_delta 0.5, Validators::Utils.similarity_score("positions", ["Council Member"], ["Councilman"]), 0.1
      assert_in_delta 0.07, Validators::Utils.similarity_score("positions", ["Mayor"], ["Council Member"]), 0.1
      assert_in_delta 0.38,
                      Validators::Utils.similarity_score("positions", ["Mayor", "Council Member"], ["Council Member"]),
                      0.05
    end

    def test_positions_similarity
      value1 = ["Council Member, District 6", "Council Member, District 7"]
      value2 = ["Council Member, District 6", "Council Member"]
      assert_in_delta 0.6, Validators::Utils.similarity_score("positions", value1, value2), 0.1
    end

    def test_positions_no_similarity
      value1 = ["Council Member, District 6"]
      value2 = ["Mayor, District 1"]
      assert_equal 0.25, Validators::Utils.similarity_score("positions", value1, value2)
    end

    def test_websites_ignore_www
      value1 = "www.example.com"
      value2 = "example.com"
      assert_equal 1.0, Validators::Utils.similarity_score("website", value1, value2)
    end

    ### TESTING DATA AGREEMENT ###
    def test_compare_people_across_sources
      result = Validators::Utils.compare_people_across_sources(@sources)

      expected_contested_people = {
        "Alice Smith" => {
          "website" => {
            disagreement_score: 0.33333333333333326,
            values: {
              "source1" => nil,
              "source2" => "alice.com",
              "source3" => "alice.org"
            }
          }
        },
        "Bob Jones" => {
          "positions" => {
            disagreement_score: 0.5714285714285714,
            values: {
              "source1" => ["Council Member"],
              "source2" => ["Councilman"],
              "source3" => ["Council Member"]
            }
          },
          "website" => {
            disagreement_score: 0.46153846153846156,
            values: {
              "source1" => "bob.com",
              "source2" => "bob-jones.com",
              "source3" => "bob.com"
            }
          }
        }
      }

      assert_equal expected_contested_people, result[:contested_people]
    end

    def test_compare_people_across_sources_with_positions
      result = Validators::Utils.compare_people_across_sources(@sources)

      expected_contested_people = {
        "Alice Smith" => {
          "website" => {
            disagreement_score: 0.33333333333333326,
            values: {
              "source1" => nil,
              "source2" => "alice.com",
              "source3" => "alice.org"
            }
          }
        },
        "Bob Jones" => {
          "positions" => {
            disagreement_score: 0.5714285714285714,
            values: {
              "source1" => ["Council Member"],
              "source2" => ["Councilman"],
              "source3" => ["Council Member"]
            }
          },
          "website" => {
            disagreement_score: 0.46153846153846156,
            values: {
              "source1" => "bob.com",
              "source2" => "bob-jones.com",
              "source3" => "bob.com"
            }
          }
        }
      }

      assert_equal expected_contested_people, result[:contested_people]
    end

    def test_compare_people_across_sources_with_different_positions
      sources = [
        {
          confidence_score: 0.9,
          source_name: "source1",
          people: [{ "name" => "Alice Smith", "positions" => ["Mayor"] }]
        },
        {
          confidence_score: 0.8,
          source_name: "source2",
          people: [{ "name" => "Alice Smith", "positions" => ["Councilman"] }]
        }
      ]

      result = Validators::Utils.compare_people_across_sources(sources)

      expected_contested_people = {
        "Alice Smith" => {
          "positions" => {
            disagreement_score: 1.0,
            values: {
              "source1" => ["Mayor"],
              "source2" => ["Councilman"]
            }
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
      assert_equal 0.5357142857142857, similarity
    end

    def test_similarity_larger_difference_in_positions
      value1 = ["Mayor"]
      value2 = ["Council Member"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # The larger the difference, the lower the similarity
      assert_in_delta 0.07, similarity, 0.02
    end

    def test_similarity_multiple_positions_comparison
      value1 = ["Council Member", "Councilman"]
      value2 = ["Councilman", "Council Member"]
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # Check that average similarity is calculated for multiple positions
      assert_equal 1.0, similarity
    end

    def test_similarity_with_nil_value
      value1 = ["Council Member"]
      value2 = nil
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      assert_equal 0.9, similarity
    end

    def test_similarity_with_mixed_nil_values
      value1 = ["Council Member"]
      value2 = []
      similarity = Validators::Utils.similarity_score("positions", value1, value2)
      # Similarity should not be penalized when one value is nil
      assert_equal 0.9, similarity
    end

    def test_merge_people_returns_array
      result = Validators::Utils.merge_people_across_sources(@sources)

      assert_instance_of Array, result
      assert_equal 2, result.size
      assert_includes result.map { |p| p["name"] }, "Alice Smith"
      assert_includes result.map { |p| p["name"] }, "Bob Jones"
    end

    def test_merge_includes_expected_fields_for_bob
      result = Validators::Utils.merge_people_across_sources(@sources)
      bob = result.find { |p| p["name"] == "Bob Jones" }

      refute_nil bob
      assert bob["positions"].is_a?(Array)
      assert_equal "bob.jones@example.com", bob["email"]
      assert_equal "555-123-4567", bob["phone_number"]
      assert bob["website"].is_a?(String)
    end

    def test_merge_includes_expected_fields_for_alice
      result = Validators::Utils.merge_people_across_sources(@sources)
      alice = result.find { |p| p["name"] == "Alice Smith" }

      refute_nil alice
      assert_equal ["Mayor"], alice["positions"]
      assert_equal "alice.smith@example.com", alice["email"]
      assert alice["website"].is_a?(String)
    end

    def test_alex_and_alexa_robinson_are_merged
      source_a = {
        confidence_score: 0.9,
        source_name: "source1",
        people: [
          { "name" => "Alex Robinson", "positions" => ["Council Member"], "email" => "alex@example.com",
            "sources" => ["https://apple.com"] }
        ]
      }

      source_b = {
        confidence_score: 0.8,
        source_name: "source2",
        people: [
          { "name" => "Alex - Robinson", "positions" => ["Councilwoman"], "email" => "alex@example.com", "sources" => ["https://peach.com"] }
        ]
      }

      sources = [source_a, source_b]

      comparison_result = Validators::Utils.compare_people_across_sources(sources)

      merged = Validators::Utils.merge_people_across_sources(sources)

      assert_equal 1, merged.length

      person = merged.first
      assert_equal "Alex Robinson", person["name"] # should resolve to canonical from source1
      assert_equal "alex@example.com", person["email"]
      assert_equal %w[https://apple.com https://peach.com], person["sources"].sort
    end

    def test_select_best_phone_number
      values = [
        { value: "123-456-7890", confidence_score: 0.8 },
        { value: "123-456-7890", confidence_score: 0.9 },
        { value: "987-654-3210", confidence_score: 0.7 }
      ]
      result = Validators::Utils.select_best_value("phone_number", values)
      assert_equal "123-456-7890", result # The most confident phone number
    end

    def test_select_best_phone_number_with_nil_values
      values = [
        { value: nil, confidence_score: 0.8 },
        { value: nil, confidence_score: 0.2 }
      ]
      result = Validators::Utils.select_best_value("phone_number", values)
      assert_nil result # No valid phone numbers
    end

    def test_select_best_email
      values = [
        { value: "test@example.com", confidence_score: 0.7 },
        { value: "test@example.com", confidence_score: 0.9 },
        { value: "other@example.com", confidence_score: 0.6 }
      ]
      result = Validators::Utils.select_best_value("email", values)
      assert_equal "test@example.com", result # The most confident email
    end

    def test_select_best_positions
      values = [
        { value: ["Manager"], confidence_score: 0.8 },
        { value: %w[Manager Developer], confidence_score: 0.9 },
        { value: ["Developer"], confidence_score: 0.7 }
      ]
      result = Validators::Utils.select_best_value("positions", values)
      assert_equal %w[Manager Developer], result # The most confident and comprehensive position list
    end

    def test_select_best_name
      values = [
        { value: "Alice Smith", confidence_score: 0.6 },
        { value: "Alice Smith", confidence_score: 0.8 },
        { value: "A. Smith", confidence_score: 0.5 }
      ]
      result = Validators::Utils.select_best_value("name", values)
      assert_equal "Alice Smith", result # The most confident version of the name
    end

    def test_select_best_email_with_all_equal_values
      values = [
        { value: "test@example.com", confidence_score: 0.8 },
        { value: "test@example.com", confidence_score: 0.9 },
        { value: "test@example.com", confidence_score: 1.0 }
      ]
      result = Validators::Utils.select_best_value("email", values)
      assert_equal "test@example.com", result # Return the most confident version
    end

    def test_find_by_name_exact_match
      people = [
        { "name" => "Alice Smith" },
        { "name" => "Bob Jones" },
        { "name" => "Charlie Brown" }
      ]

      result = Validators::Utils.find_by_name(people, "Alice Smith")
      assert_equal "Alice Smith", result["name"]
    end


    # Rename and rewrite the test for matching despite middle names/initials
    def test_find_by_name_matches_despite_middle_initials
      people = [
        { "name" => "Diana Smith" }, # Name in list has no middle initial
        { "name" => "Bob Jones" }
      ]
      # Search using a name that includes a middle initial
      result = Validators::Utils.find_by_name(people, "Diana H. Smith")
      refute_nil result, "Should find a match even with different middle initials"
      assert_equal "Diana Smith", result["name"], "Should return the matching person object"

      # Test the other way around
      people_with_initial = [
        { "name" => "Charles R. Darwin"},
        { "name" => "Gregor Mendel"}
      ]
      result_no_initial = Validators::Utils.find_by_name(people_with_initial, "Charles Darwin")
      refute_nil result_no_initial, "Should find a match even searching without middle initial"
      assert_equal "Charles R. Darwin", result_no_initial["name"], "Should return the matching person object"
    end
  end
end
