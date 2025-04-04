require "test_helper"
require_relative "../../../lib/tasks/city_scrape/city_manager"

class CityScrape::CityManagerTest < Minitest::Test
  def test_merges_new_people_into_existing_directory
    city_directory = [
      {
        "name" => "John Smith",
        "image" => "images/1234.jpg",
        "contact_details" => [
          {
            "type" => "email",
            "value" => "john@city.gov"
          }
        ],
        "other_names" => [
          {
            "note" => nil,
            "name" => "Mayor",
            "start_date" => "2020-01-01",
            "end_date" => "2024-12-31"
          }
        ],
        "updated_at" => "2025-03-30",
        "created_at" => "2025-03-30",
        "sources" => [
          {
            "url" => "https://example.com/council",
            "note" => nil
          }
        ]
      }
    ]

    partial_directory = [
      {
        "name" => "John Smith",
        "contact_details" => [
          { "type" => "phone", "value" => "123-456-7890" }
        ],
        "updated_at" => "2025-04-30",
        "created_at" => "2025-04-30",
        "sources" => [
          {
            "url" => "https://example.com/council_updated",
            "note" => nil
          }
        ]
      },
      {
        "name" => "Jane Doe",
        "contact_details" => [
          {
            "type" => "email",
            "value" => "jane@city.gov"
          }
        ],
        "updated_at" => "2025-04-30",
        "created_at" => "2025-04-30",
        "sources" => [
          {
            "url" => "https://example.com/council",
            "note" => nil
          }
        ]
      }
    ]

    expected = [
      {
        "name" => "John Smith",
        "image" => "images/1234.jpg",
        "contact_details" => [
          { "type" => "email", "value" => "john@city.gov" },
          { "type" => "phone", "value" => "123-456-7890" }
        ],
        "other_names" => [
          { "note" => nil, "name" => "Mayor", "start_date" => "2020-01-01", "end_date" => "2024-12-31" }
        ],
        "updated_at" => "2025-04-30",
        "created_at" => "2025-04-30",
        "sources" => [
          { "url" => "https://example.com/council", "note" => nil },
          { "url" => "https://example.com/council_updated", "note" => nil }
        ]
      },
      {
        "name" => "Jane Doe",
        "contact_details" => [
          { "type" => "email", "value" => "jane@city.gov" }
        ]
      }
    ]

    result = CityScrape::CityManager.merge_directory(city_directory, partial_directory)

    assert_equal 2, result.length
    john = result.find { |person| person["name"] == "John Smith" }
    jane = result.find { |person| person["name"] == "Jane Doe" }

    assert_equal "images/1234.jpg", john["image"]
    assert_equal "123-456-7890", john["contact_details"].find { |detail| detail["type"] == "phone" }["value"]
    assert_equal "john@city.gov", john["contact_details"].find { |detail| detail["type"] == "email" }["value"]
    assert_equal "Mayor", john["other_names"].first["name"]
    assert_equal "2020-01-01", john["other_names"].first["start_date"]
    assert_equal "2024-12-31", john["other_names"].first["end_date"]
    assert_equal "2025-04-30", john["updated_at"]
    assert_equal "2025-04-30", john["created_at"]
    assert_equal "https://example.com/council", john["sources"].first["url"]
    assert_equal "https://example.com/council_updated", john["sources"].last["url"]

    assert_equal "2025-04-30", jane["updated_at"]
    assert_equal "2025-04-30", jane["created_at"]
    assert_equal "jane@city.gov", jane["contact_details"].first["value"]
    assert_equal "2025-04-30", jane["updated_at"]
    assert_equal "2025-04-30", jane["created_at"]
    assert_equal "https://example.com/council", jane["sources"].first["url"]
  end

  def test_preserves_existing_data_when_merging
    city_directory = [
      { "name" => "John Smith", "email" => "john@city.gov" }
    ]

    partial_directory = [
      { "name" => "John Smith", "email" => "different@email.com" }
    ]

    result = CityScrape::CityManager.merge_directory(city_directory, partial_directory)

    assert_equal "john@city.gov", result.first["email"]
  end

  def test_handles_array_values_correctly
    city_directory = [
      {
        "name" => "John Smith",
        "other_names" => [
          { "name" => "Mayor", "note" => "position" }
        ]
      }
    ]

    partial_directory = [
      {
        "name" => "John Smith",
        "other_names" => [
          { "name" => "Council Member", "note" => "position" }
        ]
      }
    ]

    result = CityScrape::CityManager.merge_directory(city_directory, partial_directory)

    expected_positions = [
      { "name" => "Mayor", "note" => "position" },
      { "name" => "Council Member", "note" => "position" }
    ]

    assert_equal expected_positions,
                 result.first["other_names"],
                 "Should merge and sort other_names correctly"
  end

  def test_adds_source_url_to_sources_array
    city_directory = [
      { "name" => "John Smith", "sources" => [{ "url" => "https://old-source.com" }] }
    ]

    partial_directory = [
      { "name" => "John Smith", "sources" => [{ "url" => "https://new-source.com" }] }
    ]

    new_url = "https://new-source.com"
    result = CityScrape::CityManager.merge_directory(city_directory, partial_directory)

    john = result.find { |person| person["name"] == "John Smith" }

    puts "john: #{john.inspect}"
    assert_equal 2, john["sources"].length, "Should have exactly two sources"
  end

  def test_handles_empty_directories
    city_directory = []
    partial_directory = []

    result = CityScrape::CityManager.merge_directory(city_directory, partial_directory)

    assert_empty result, "People array should be empty"
  end

  def test_sorts_by_positions
    positions = [
      { "name" => "District 5 Representative" },
      { "name" => "Council Member" },
      { "name" => "Mayor" },
      { "name" => "Council President" },
      { "name" => "At Large Member" }
    ]

    sorted = CityScrape::CityManager.sort_by_positions(positions)

    assert_equal "Mayor", sorted[0]["name"], "Mayor should be first"
    assert_equal "Council President", sorted[1]["name"], "Council President should be second"
    assert_equal "Council Member", sorted[2]["name"], "Council Member should be third"
    assert_equal ["At Large Member", "District 5 Representative"],
                 sorted[3..4].map { |p| p["name"] }.sort,
                 "Other positions should be alphabetical"
  end

  def test_sorts_people_by_other_names_position
    people = [
      {
        "name" => "Bob Wilson",
        "other_names" => [{ "name" => "Council member", "note" => "position" }]
      },
      {
        "name" => "Alice Smith",
        "other_names" => [{ "name" => "Mayor", "note" => "position" }]
      },
      {
        "name" => "Charlie Brown",
        "other_names" => [{ "name" => "Council President", "note" => "position" }]
      },
      {
        "name" => "David Jones",
        "other_names" => [{ "name" => "District 5 Representative", "note" => "position" }]
      }
    ]

    sorted = CityScrape::CityManager.sort_people(people)

    assert_equal "Alice Smith", sorted[0]["name"], "Mayor should be first"
    assert_equal "Charlie Brown", sorted[1]["name"], "Council President should be second"
    assert_equal "Bob Wilson", sorted[2]["name"], "Council Member should be third"
    assert_equal "David Jones", sorted[3]["name"], "Other positions should be last"
  end
end
