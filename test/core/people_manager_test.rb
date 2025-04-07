require "test_helper"
require "core/people_manager"

class PeopleManagerTest < Minitest::Test
  def setup
    @positions_config = [
      { "role" => "mayor" },
      { "role" => "deputy mayor" },
      { "role" => "council president" },
      { "role" => "council member", "aliases" => ["councilmember"] }
    ]

    @people = [
      { "name" => "Alice", "positions" => ["council member", "mayor"] },
      { "name" => "Bob", "positions" => [] },
      { "name" => "Charlie", "positions" => ["councilmember"] }
    ]
  end

  def test_filters_out_people_with_no_positions
    result = Core::PeopleManager.format_people(@people, @positions_config)
    names = result.map { |p| p["name"] }
    refute_includes names, "Bob"
  end

  def test_sorts_and_formats_positions
    result = Core::PeopleManager.format_people(@people, @positions_config)
    alice = result.find { |p| p["name"] == "Alice" }
    assert_equal ["Mayor", "Council Member"], alice["positions"]
  end

  def test_handles_aliases
    result = Core::PeopleManager.format_people(@people, @positions_config)
    charlie = result.find { |p| p["name"] == "Charlie" }
    assert_equal ["Council Member"], charlie["positions"]
  end

  def test_format_people_with_multiple_positions
    # Sample input data
    people = [
      {
        "name" => "Sara Nelson",
        "image" => "images/a32c94a54ec5035b308cb1529e264a28c2c9915e703a870d571ba03850ecb93f.jpg",
        "positions" => ["council president", "council member"],
        "email" => "Sara.Nelson@seattle.gov",
        "phone_number" => "(206) 684-8809",
        "website" => "https://seattle.gov/council/meet-the-council/sara-nelson",
        "sources" => ["https://seattle.gov/council"]
      },
      {
        "name" => "Joy Hollingsworth",
        "image" => "images/d2054dbd6443343a0f29948c9e1596e442427079bfd0b4ed1989d71e67a662ac.jpg",
        "positions" => ["council member", "district 3"],
        "email" => "Joy.Hollingsworth@seattle.gov",
        "phone_number" => "206-684-8803",
        "website" => "https://seattle.gov/council/hollingsworth",
        "sources" => ["https://seattle.gov/council"]
      },
      {
        "name" => "Bruce Harrell",
        "image" => "images/ae297f8bf7650b66f3e5267ccc06abf23234a9c4acb178cb3abad7f800c199ce.jpg",
        "positions" => ["mayor"],
        "email" => "",
        "phone_number" => "(206) 684-4000",
        "website" => "https://seattle.gov/mayor",
        "sources" => ["https://harrell.seattle.gov//"]
      }
    ]

    positions_config = [
      { "role" => "mayor" },
      { "role" => "council president" },
      { "role" => "council member", "aliases" => ["councilmember"], "divisions" => ["district"] }
    ]

    # Call the method with test data
    formatted = Core::PeopleManager.format_people(people, positions_config)

    # Assert that the formatted list has only the relevant entries
    assert_equal 3, formatted.size

    File.write("chat.txt", formatted, mode: "a")

    # Assert that Bruce Harrell's position is "Mayor"
    assert_equal formatted[0]["positions"], ["Mayor"]

    # Assert that Joy Hollingsworth's district is preserved
    assert_includes formatted[2]["positions"], "District 3"

    # Assert that Sara Nelson's position is correctly formatted
    assert_includes formatted[1]["positions"], "Council President"
    assert_includes formatted[1]["positions"], "Council Member"
  end
end
