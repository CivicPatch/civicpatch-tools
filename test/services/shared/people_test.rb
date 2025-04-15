require "test_helper"
require_relative "../../../lib/services/shared/people"

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
          "term_dates" => [{ "data" => "2025-01-01", "source" => nil }]
        }

        # This represents a partial person (with singular field names)
        @partial_person_with_data_points = {
          "name" => "John Doe",
          "phone_number" => { "data" => "123-456-7890", "source" => nil },
          "email" => { "data" => "john@example.com", "source" => nil },
          "website" => { "data" => "https://example.com", "source" => nil },
          "term_date" => { "data" => "2025-01-01", "source" => nil },
          "positions" => ["Mayor"]
        }

        @person_without_data_points = {
          "name" => "Jane Smith",
          "positions" => [],
          "phone_numbers" => [],
          "emails" => [],
          "websites" => [],
          "term_dates" => []
        }

        @partial_person_without_data_points = {
          "name" => "Jane Smith",
          "phone_number" => nil,
          "email" => nil,
          "website" => nil,
          "term_date" => nil,
          "positions" => []
        }
      end

      def test_collect_people_new_person
        people = []
        partial_people = [@partial_person_with_data_points]

        result = People.collect_people(people, partial_people)

        assert_equal 1, result.length
        collected_person = result.first
        assert_equal "John Doe", collected_person["name"]
        assert_equal 1, collected_person["phone_numbers"].length
        assert_equal "123-456-7890", collected_person["phone_numbers"].first["data"]
      end

      def test_collect_people_merge_existing
        people = [@person_with_data_points]

        # Create a partial person with the same name but different data
        partial_person = {
          "name" => "John Doe",
          "phone_number" => { "data" => "987-654-3210", "source" => nil },
          "positions" => ["Vice Mayor"]
        }

        result = People.collect_people(people, [partial_person])

        assert_equal 1, result.length
        merged_person = result.first
        assert_equal "John Doe", merged_person["name"]
        assert_equal 2, merged_person["phone_numbers"].length

        # Test that positions were merged and uniqued
        assert_equal 2, merged_person["positions"].length
        assert_includes merged_person["positions"], "Mayor"
        assert_includes merged_person["positions"], "Vice Mayor"

        # Test the position we added with a duplicate
        duplicate_position = {
          "name" => "John Doe",
          "positions" => ["Mayor", "Council Member"]
        }

        result = People.collect_people(result, [duplicate_position])
        merged_person = result.first

        # Should have 3 unique positions now
        assert_equal 3, merged_person["positions"].length
        assert_includes merged_person["positions"], "Mayor"
        assert_includes merged_person["positions"], "Vice Mayor"
        assert_includes merged_person["positions"], "Council Member"
      end

      def test_data_points_with_source
        source = "city_website"
        person = @partial_person_with_data_points.dup

        # Capture puts output to verify implementation
        output = capture_io do
          People.data_points_with_source(person, source)
        end

        # Verify it logged the expected messages
        assert_includes output.join, "Adding source to phone_number"
        assert_includes output.join, "Adding source to email"
        assert_includes output.join, "Adding source to website"
        assert_includes output.join, "Adding source to term_date"

        # Verify sources were assigned correctly
        %w[phone_number email website term_date].each do |data_point|
          assert_equal source, person[data_point]["source"]
        end
      end

      def test_data_points_with_source_no_data_points
        source = "city_website"
        person = @partial_person_without_data_points.dup
        result = People.data_points_with_source(person, source)

        assert_equal person, result
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

        output = capture_io do
          assert People.contact_data_points_present?(person)
        end

        assert_includes output.join, "Checking if data points are present for John Doe"
      end

      def test_contact_data_points_present_with_all_types
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [{ "data" => "test@example.com" }],
          "websites" => [{ "data" => "https://example.com" }]
        }

        output = capture_io do
          assert People.contact_data_points_present?(person)
        end

        assert_includes output.join, "Checking if data points are present for John Doe"
      end

      def test_contact_data_points_not_present_with_one_type
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          "emails" => [],
          "websites" => []
        }

        output = capture_io do
          refute People.contact_data_points_present?(person)
        end

        assert_includes output.join, "Checking if data points are present for John Doe"
      end

      def test_without_empty_data_points
        person = {
          "name" => "John Doe",
          "phone_numbers" => [{ "data" => "123-456-7890" }, nil, { "data" => "" }],
          "emails" => [{ "data" => "test@example.com" }, { "data" => nil }],
          "websites" => [{ "data" => "https://example.com" }],
          "term_dates" => [{ "data" => "2025-01-01" }, {}]
        }

        result = People.without_empty_data_points(person)

        # Verify correct count of remaining items
        assert_equal 1, result["phone_numbers"].length
        assert_equal 1, result["emails"].length
        assert_equal 1, result["websites"].length
        assert_equal 1, result["term_dates"].length

        # Verify the actual values of the remaining items
        assert_equal "123-456-7890", result["phone_numbers"].first["data"]
        assert_equal "test@example.com", result["emails"].first["data"]
        assert_equal "https://example.com", result["websites"].first["data"]
        assert_equal "2025-01-01", result["term_dates"].first["data"]

        # Ensure original person name is preserved
        assert_equal "John Doe", result["name"]
      end

      def test_without_empty_data_points_missing_fields
        # Test when some fields are completely missing from the person
        person = {
          "name" => "Jane Smith",
          "phone_numbers" => [{ "data" => "123-456-7890" }],
          # emails field is missing
          "websites" => []
          # term_dates field is missing
        }

        result = People.without_empty_data_points(person)

        # Verify the method doesn't error on missing fields
        assert_equal 1, result["phone_numbers"].length
        assert_equal "123-456-7890", result["phone_numbers"].first["data"]
        assert_empty result["websites"]
        assert_equal "Jane Smith", result["name"]
      end

      def test_without_empty_data_points_all_empty
        # Test when all data points are empty or nil
        person = {
          "name" => "Empty Person",
          "phone_numbers" => [nil, { "data" => "" }],
          "emails" => [{ "data" => nil }],
          "websites" => [{}],
          "term_dates" => []
        }

        result = People.without_empty_data_points(person)

        # All arrays should be empty but still exist
        assert_empty result["phone_numbers"]
        assert_empty result["emails"]
        assert_empty result["websites"]
        assert_empty result["term_dates"]
        assert_equal "Empty Person", result["name"]
      end
    end
  end
end
