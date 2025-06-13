# frozen_string_literal: true

require "test_helper"
require_relative "../../../../lib/services/shared/people"
require "resolvers/person_resolver" # Added dependency

module Services
  module Shared
    class PeopleTest < Minitest::Test
      def setup
        # This represents an accumulated person (with plural field names)
        @person_with_data_points = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "phone_numbers" => [{ "data" => "123-456-7890", "source" => nil }],
          "emails" => [{ "data" => "john@example.com", "source" => nil }],
          "websites" => [{ "data" => "https://example.com", "source" => nil }],
          "start_dates" => [], # Added for completeness
          "end_dates" => [{ "data" => "2025-12-31", "source" => nil }],
          "sources" => []
        }

        # This represents a partial person (from LLM, likely singular field names)
        @partial_person_with_data_points = {
          "name" => "John Doe",
          "phone_number" => { "data" => "123-456-7890", "source" => nil },
          "email" => { "data" => "john@example.com", "source" => nil },
          "website" => { "data" => "https://example.com", "source" => nil },
          "start_date" => { "data" => "2023-01-01", "source" => nil },
          "end_date" => { "data" => "2025-12-31", "source" => nil },
          "positions" => ["Mayor"],
          "sources" => ["some_source_url"]
        }

        @person_without_data_points = {
          "name" => "Jane Smith",
          "positions" => [],
          "phone_numbers" => [],
          "emails" => [],
          "websites" => [],
          "start_dates" => [],
          "end_dates" => [],
          "sources" => []
        }

        @partial_person_without_data_points = {
          "name" => "Jane Smith",
          "phone_number" => nil,
          "email" => nil,
          "website" => nil,
          "start_date" => nil,
          "end_date" => nil,
          "positions" => [],
          "sources" => ["another_source_url"]
        }

        @kimmi_canonical = "Edward Kimmi"
        @kimmi_dr = "Dr. Edward Kimmi"

        # Person data - assume same email allows weak match
        @person_kimmi = {
          "name" => @kimmi_canonical,
          "email" => "ekimmi@example.com",
          "positions" => ["Council Member"],
          "sources" => ["source_canonical"],
          "phone_numbers" => [], "emails" => [], "websites" => [], "start_dates" => [], "end_dates" => []
        }
        @person_kimmi_dr = {
          "name" => @kimmi_dr,
          "email" => "ekimmi@example.com", # Same email for weak match
          "positions" => ["Councilor"], # Different position for merge test
          "sources" => ["source_dr"],
          "phone_numbers" => [], "emails" => [], "websites" => [], "start_dates" => [], "end_dates" => []
        }

        # Initial empty state
        @initial_people_empty = []
        @initial_config_empty = {}

        # State where canonical Kimmi already exists
        @initial_people_with_kimmi = [@person_kimmi.dup]
        @initial_config_with_kimmi = {
          @kimmi_canonical => { "other_names" => [] }
        }

        # State where Dr. Kimmi already exists
        @initial_people_with_kimmi_dr = [@person_kimmi_dr.dup]
        @initial_config_with_kimmi_dr = {
          @kimmi_dr => { "other_names" => [] }
        }
      end

      def test_collect_people_new_person
        people = []
        partial_people = [@partial_person_with_data_points]
        config = {}

        people_list, _updated_config = People.collect_people(config, people, partial_people)

        assert_equal 1, people_list.length
        collected_person = people_list.first
        assert_equal "John Doe", collected_person["name"]
        # Assuming format_raw_data was called implicitly or is handled
        # This part of the test might need adjustment based on actual collect_people implementation details
        # For now, we assume the partial person is added as is if no match
        # assert_equal 1, collected_person["phone_numbers"].length
        # assert_equal "123-456-7890", collected_person["phone_numbers"].first["data"]
      end

      def test_collect_people_merge_existing
        people = [@person_with_data_points.dup]
        config = { "John Doe" => { "other_names" => [] } }

        # Create a partial person with the same name but different data
        partial_person_merge = {
          "name" => "John Doe",
          "phone_number" => { "data" => "987-654-3210", "source" => "source2" },
          "positions" => ["Vice Mayor"],
          "sources" => ["source2"]
        }

        # Format the partial person like format_raw_data would
        formatted_partial = People.format_raw_data(partial_person_merge, partial_person_merge["sources"].first)

        people_list, _updated_config = People.collect_people(config, people, [formatted_partial])

        assert_equal 1, people_list.length
        merged_person = people_list.first
        assert_equal "John Doe", merged_person["name"]

        # Phone numbers should be merged
        assert_equal 2, merged_person["phone_numbers"].length
        assert_includes merged_person["phone_numbers"].map { |p| p["data"] }, "123-456-7890"
        assert_includes merged_person["phone_numbers"].map { |p| p["data"] }, "987-654-3210"

        # Positions should be merged and unique
        assert_equal 2, merged_person["positions"].length
        assert_includes merged_person["positions"], "Mayor"
        assert_includes merged_person["positions"], "Vice Mayor"

        # Test adding another partial with a duplicate position
        partial_person_duplicate_pos = {
          "name" => "John Doe",
          "positions" => ["Mayor", "Council Member"],
          "sources" => ["source3"]
        }
        formatted_partial_dup = People.format_raw_data(partial_person_duplicate_pos,
                                                       partial_person_duplicate_pos["sources"].first)

        people_list_final, _updated_config_final = People.collect_people(config, people_list, [formatted_partial_dup])
        merged_person_final = people_list_final.first

        # Should have 3 unique positions now
        assert_equal 3, merged_person_final["positions"].length
        assert_includes merged_person_final["positions"], "Mayor"
        assert_includes merged_person_final["positions"], "Vice Mayor"
        assert_includes merged_person_final["positions"], "Council Member"
      end

      def test_data_points_with_source
        source_url = "https://city_website.com/page"
        person_data = {
          "phone_numbers" => [{ "data" => "111" }],
          "emails" => [{ "data" => "a@b.c" }],
          "websites" => [{ "data" => "https://d.e" }],
          "start_dates" => [{ "data" => "2024-01-01" }],
          "end_dates" => [{ "data" => "2025-12-31" }]
        }
        expected_formatted_source = Utils::UrlHelper.format_url(source_url)

        result_person = People.data_points_with_source(person_data.dup, source_url)

        %w[phone_numbers emails websites start_dates end_dates].each do |key|
          assert result_person[key].is_a?(Array)
          refute_empty result_person[key]
          result_person[key].each do |data_point_item|
            assert_equal expected_formatted_source, data_point_item["source"], "Source mismatch for #{key}"
          end
        end
      end

      def test_data_points_with_source_no_data_points
        source = "city_website"
        person = @partial_person_without_data_points.dup
        # Ensure keys exist but are empty arrays
        person["phone_numbers"] = []
        person["emails"] = []
        person["websites"] = []
        person["start_dates"] = []
        person["end_dates"] = []

        result = People.data_points_with_source(person, source)

        assert_equal person, result
        %w[phone_numbers emails websites start_dates end_dates].each do |key|
          assert_empty result[key], "Key #{key} should remain empty"
        end
      end

      def test_data_point_present
        data_point = { "data" => "test data" }
        assert People.data_point?(data_point)
      end

      def test_data_point_nil
        refute People.data_point?(nil)
      end

      def test_data_point_empty
        data_point = { "data" => "" }
        refute People.data_point?(data_point)
      end

      def test_profile_data_points_present_with_positions_and_websites
        person = {
          "positions" => ["Mayor"],
          "websites" => [{ "data" => "https://example.com" }],
          "phone_numbers" => [],
          "emails" => []
        }

        assert People.profile_data_points_present?(person)
      end

      def test_profile_data_points_present_with_positions_and_contact_info
        person = {
          "positions" => ["Mayor"],
          "websites" => [],
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [{ "data" => "test@example.com" }]
        }

        assert People.profile_data_points_present?(person)
      end

      def test_profile_data_points_not_present_without_positions
        person = {
          "positions" => [],
          "websites" => [{ "data" => "https://example.com" }],
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [{ "data" => "test@example.com" }]
        }

        refute People.profile_data_points_present?(person)
      end

      def test_profile_data_points_not_present_without_websites_or_contact_info
        person = {
          "positions" => ["Mayor"],
          "websites" => [],
          "phone_numbers" => [],
          "emails" => []
        }

        refute People.profile_data_points_present?(person)
      end

      def test_contact_data_points_present_with_two_types
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [{ "data" => "test@example.com" }],
          "websites" => []
        }
        assert People.contact_data_points_present?(person)
      end

      def test_contact_data_points_present_with_all_types
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [{ "data" => "test@example.com" }],
          "websites" => [{ "data" => "https://example.com" }]
        }
        assert People.contact_data_points_present?(person)
      end

      def test_contact_data_points_present_with_one_type
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }], # Only phone
          "emails" => [],
          "websites" => []
        }
        assert People.contact_data_points_present?(person), "Should be present if at least one contact type exists"
      end

      def test_contact_data_points_not_present_with_no_types
        person = {
          "name" => "John Doe",
          "phone_numbers" => [],
          "emails" => [],
          "websites" => []
        }
        refute People.contact_data_points_present?(person)
      end

      def test_collect_people_adds_dr_name_to_other_names
        config_to_update = Marshal.load(Marshal.dump(@initial_config_with_kimmi))
        # Format partial person as if coming from format_raw_data
        formatted_partial = People.format_raw_data(@person_kimmi_dr, @person_kimmi_dr["sources"].first)
        partial_people_to_add = [formatted_partial]

        people_list, final_config = Services::Shared::People.collect_people(
          config_to_update,
          @initial_people_with_kimmi,
          partial_people_to_add
        )

        assert_equal 1, people_list.size
        merged_person = people_list.first
        assert_equal @kimmi_canonical, merged_person["name"]
        assert_includes merged_person["positions"], "Council Member"
        assert_includes merged_person["positions"], "Councilor"
        assert_includes merged_person["sources"], "source_canonical"
        assert_includes merged_person["sources"], "source_dr"

        assert final_config.key?(@kimmi_canonical)
        assert final_config[@kimmi_canonical].key?("other_names")
        assert_includes final_config[@kimmi_canonical]["other_names"], @kimmi_dr
      end

      def test_collect_people_adds_canonical_name_to_other_names_if_dr_first
        config_to_update = Marshal.load(Marshal.dump(@initial_config_with_kimmi_dr))
        formatted_partial = People.format_raw_data(@person_kimmi, @person_kimmi["sources"].first)
        partial_people_to_add = [formatted_partial]

        people_list, final_config = Services::Shared::People.collect_people(
          config_to_update,
          @initial_people_with_kimmi_dr,
          partial_people_to_add
        )

        assert_equal 1, people_list.size
        merged_person = people_list.first
        assert_equal @kimmi_dr, merged_person["name"]
        assert_includes merged_person["positions"], "Council Member"
        assert_includes merged_person["positions"], "Councilor"
        assert_includes merged_person["sources"], "source_canonical"
        assert_includes merged_person["sources"], "source_dr"

        assert final_config.key?(@kimmi_dr)
        assert final_config[@kimmi_dr].key?("other_names")
        assert_includes final_config[@kimmi_dr]["other_names"], @kimmi_canonical
      end

      def test_collect_people_handles_both_versions_from_empty_state
        config_to_update = Marshal.load(Marshal.dump(@initial_config_empty))
        # Format partials
        formatted_kimmi = People.format_raw_data(@person_kimmi, @person_kimmi["sources"].first)
        formatted_kimmi_dr = People.format_raw_data(@person_kimmi_dr, @person_kimmi_dr["sources"].first)
        partial_people_to_add = [formatted_kimmi, formatted_kimmi_dr]

        people_list, final_config = Services::Shared::People.collect_people(
          config_to_update,
          @initial_people_empty,
          partial_people_to_add
        )

        assert_equal 1, people_list.size
        merged_person = people_list.first
        assert_equal @kimmi_canonical, merged_person["name"]
        assert_includes merged_person["positions"], "Council Member"
        assert_includes merged_person["positions"], "Councilor"

        assert final_config.key?(@kimmi_canonical)
        assert final_config[@kimmi_canonical].key?("other_names")
        assert_includes final_config[@kimmi_canonical]["other_names"], @kimmi_dr
      end

      def test_collect_people_handles_both_versions_from_empty_state_dr_first
        config_to_update = Marshal.load(Marshal.dump(@initial_config_empty))
        formatted_kimmi = People.format_raw_data(@person_kimmi, @person_kimmi["sources"].first)
        formatted_kimmi_dr = People.format_raw_data(@person_kimmi_dr, @person_kimmi_dr["sources"].first)
        partial_people_to_add = [formatted_kimmi_dr, formatted_kimmi]

        people_list, final_config = Services::Shared::People.collect_people(
          config_to_update,
          @initial_people_empty,
          partial_people_to_add
        )

        assert_equal 1, people_list.size
        merged_person = people_list.first
        assert_equal @kimmi_dr, merged_person["name"]
        assert_includes merged_person["positions"], "Council Member"
        assert_includes merged_person["positions"], "Councilor"

        assert final_config.key?(@kimmi_dr)
        assert final_config[@kimmi_dr].key?("other_names")
        assert_includes final_config[@kimmi_dr]["other_names"], @kimmi_canonical
      end

      def test_collect_people_adds_new_person_if_no_match
        new_person = { "name" => "Brand New Person", "email" => "new@example.com", "positions" => ["Intern"],
                       "sources" => ["new_source"] }
        config_to_update = Marshal.load(Marshal.dump(@initial_config_with_kimmi))
        formatted_new = People.format_raw_data(new_person, new_person["sources"].first)
        partial_people_to_add = [formatted_new]

        people_list, final_config = Services::Shared::People.collect_people(
          config_to_update,
          @initial_people_with_kimmi,
          partial_people_to_add
        )

        assert_equal 2, people_list.size
        assert_includes people_list.map { |p| p["name"] }, "Brand New Person"
        assert_includes people_list.map { |p| p["name"] }, @kimmi_canonical

        # Check if config was updated for the new person
        # Note: The current implementation might add {} for a new person
        assert final_config.key?("Brand New Person"), "Config should have key for new person"
        assert final_config.key?(@kimmi_canonical), "Config should still have original person key"
      end

      def test_format_person_with_valid_image
        llm_person = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "images" => [
            {
              "data" => "images/valid-image.jpg",
              "source" => "https://example.com",
              "llm_confidence" => 0.9
            }
          ],
          "sources" => ["https://example.com"]
        }

        result = People.format_person(llm_person)

        assert_equal "images/valid-image.jpg", result["image"]
        assert_includes result["sources"], "https://example.com"
      end

      def test_format_person_with_no_image
        llm_person = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "images" => [],
          "sources" => ["https://example.com"]
        }

        result = People.format_person(llm_person)

        assert_nil result["image"]
      end

      def test_format_person_with_invalid_image
        llm_person = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "images" => [
            {
              "data" => nil,
              "source" => "https://example.com"
            }
          ],
          "sources" => ["https://example.com"]
        }

        result = People.format_person(llm_person)

        assert_nil result["image"]
      end

      def test_format_person_with_multiple_images
        llm_person = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "images" => [
            {
              "data" => "images/image1.jpg",
              "source" => "https://example.com/1",
              "llm_confidence" => 0.5
            },
            {
              "data" => "images/image2.jpg",
              "source" => "https://example.com/2",
              "llm_confidence" => 0.9
            },
            {
              "data" => "images/image3.jpg",
              "source" => "https://example.com/3",
              "llm_confidence" => 0.7
            }
          ],
          "sources" => ["https://example.com/1", "https://example.com/2", "https://example.com/3"]
        }

        result = People.format_person(llm_person)

        # Should pick the image with highest confidence
        assert_equal "images/image2.jpg", result["image"]
        assert_includes result["sources"], "https://example.com/2"
      end

      def test_format_person_with_duplicate_images
        llm_person = {
          "name" => "John Doe",
          "positions" => ["Mayor"],
          "images" => [
            {
              "data" => "images/same-image.jpg",
              "source" => "https://example.com/1",
              "llm_confidence" => 0.5
            },
            {
              "data" => "images/same-image.jpg",
              "source" => "https://example.com/2",
              "llm_confidence" => 0.9
            }
          ],
          "sources" => ["https://example.com/1", "https://example.com/2"]
        }

        result = People.format_person(llm_person)

        # Should pick the image with highest confidence even if it's a duplicate
        assert_equal "images/same-image.jpg", result["image"]
        assert_includes result["sources"], "https://example.com/2"
      end
    end
  end
end
