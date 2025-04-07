require "test_helper"
require "core/person_manager/utils"

class CorePersonManagerUtilsTest < Minitest::Test
  def setup
    # Example positions_config with roles, aliases, and divisions
    @positions_config = [
      { "role" => "mayor" },
      { "role" => "deputy mayor" },
      { "role" => "council president" },
      { "role" => "council vice president" },
      { "role" => "council manager" },
      { "role" => "council member", "aliases" => ["councilmember"],
        "divisions" => %w[at-large ward district seat position] }
    ]

    @positions_config_sorted = [
      { "role" => "mayor" },
      { "role" => "deputy mayor", "divisions" => ["district"] },
      { "role" => "council member", "divisions" => %w[position seat ward] }
    ]

    @people = [
      { "name" => "Armondo Pavone", "positions" => ["mayor"] },
      { "name" => "James Alberson, Jr.", "positions" => ["council member", "council president", "position 1"] },
      { "name" => "Carmen Rivera", "positions" => ["council member", "position 2"] },
      { "name" => "Ed Prince", "positions" => ["council member", "position 5"] },
      { "name" => "Kim-Khánh Văn", "positions" => ["council member", "position 7"] },
      { "name" => "Ruth Pérez", "positions" => ["council member"] },
      { "name" => "Ryan McIrvin", "positions" => ["council member", "position 4"] },
      { "name" => "Valerie O'Halloran", "positions" => ["council member", "position 3"] }
    ]
  end

  def test_normalize_role
    positions = ["mayor"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["mayor"], normalized
  end

  def test_normalize_role_with_alias
    positions = ["councilmember"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member"], normalized
  end

  def test_normalize_position_with_division
    positions = ["position #4", "council member, ward 1"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member", "position 4", "ward 1"], normalized
  end

  def test_normalize_position_with_division_alias
    positions = ["councilmember at-large"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member", "at-large"], normalized
  end

  def test_normalize_position_with_district_division
    positions = ["councilmember district 3"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member", "district 3"], normalized
  end

  def test_normalize_multiple_positions
    positions = ["mayor", "councilmember at-large", "councilmember district 3", "position #4"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["mayor", "council member", "at-large", "district 3", "position 4"],
                 normalized
  end

  def test_position_with_invalid_division
    positions = ["councilmember invalid"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member"], normalized
  end

  def test_position_with_duplicate_substring
    positions = ["mayor", "deputy mayor"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["mayor", "deputy mayor"], normalized
  end

  # position sort
  def test_sorts_positions_by_role_order
    positions = ["councilmember district", "mayor", "deputy mayor"]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal ["mayor", "deputy mayor", "council member", "district"], sorted
  end

  def test_sort_positions_multiple_roles
    positions = [
      "council member",
      "council president"
    ]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal [
      "council president",
      "council member"
    ], sorted
  end

  def test_sorts_positions_by_role_then_division_order
    positions = [
      "councilmember district",
      "councilmember at-large",
      "councilmember ward"
    ]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal [
      "council member",
      "at-large",
      "district",
      "ward"
    ], sorted
  end

  def test_sorts_alphabetically_if_roles_and_divisions_are_the_same
    positions = [
      "councilmember seat",
      "councilmember district",
      "councilmember at-large"
    ]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal [
      "council member",
      "at-large",
      "district",
      "seat"
    ], sorted
  end

  def test_handles_roles_with_missing_divisions
    positions = ["councilmember", "councilmember at-large", "councilmember seat"]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal ["council member", "at-large", "seat"], sorted
  end

  #
  ## Sort People
  #
  def test_sort_people_by_role_order
    people = [
      { "name" => "Armondo Pavone", "positions" => ["Mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["Council Member"] },
      { "name" => "Ed Prince", "positions" => ["Council Member", "Chair"] }
    ]

    sorted_people = Core::PersonManager::Utils.sort_people(people, @positions_config_sorted)

    expected = [
      { "name" => "Armondo Pavone", "positions" => ["Mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["Council Member"] },
      { "name" => "Ed Prince", "positions" => ["Council Member", "Chair"] }
    ]

    assert_equal expected, sorted_people
  end

  def test_sort_people_with_divisions
    people = [
      { "name" => "Armondo Pavone", "positions" => ["Mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["Council Member, Ward 1", "random"] },
      { "name" => "Ed Prince", "positions" => ["Council Member, Ward 2"] }
    ]

    sorted_people = Core::PersonManager::Utils.sort_people(people, @positions_config_sorted)

    expected = [
      { "name" => "Armondo Pavone", "positions" => ["Mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["Council Member, Ward 1", "random"] },
      { "name" => "Ed Prince", "positions" => ["Council Member, Ward 2"] }
    ]

    assert_equal expected, sorted_people
  end

  def test_sort_people_with_case_insensitivity
    people = [
      { "name" => "Armondo Pavone", "positions" => ["mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["council member"] }
    ]

    sorted_people = Core::PersonManager::Utils.sort_people(people, @positions_config_sorted)

    expected = [
      { "name" => "Armondo Pavone", "positions" => ["mayor"] },
      { "name" => "Carmen Rivera", "positions" => ["council member"] }
    ]

    assert_equal expected, sorted_people
  end

  def test_sort_order_by_role_then_division_then_name
    sorted_people = Core::PersonManager::Utils.sort_people(@people, @positions_config)

    # Expected order based on the provided data:
    # 1. Mayor (Armondo Pavone) comes first because mayor has the top role.
    # 2. Then council members sorted by the alphabetical order of their division label:
    #    "position 1", "position 2", "position 3", "position 4", "position 5", "position 7"
    # 3. For people without a specific division (only "council member"), those will sort after those with a division.
    expected_order = [
      "Armondo Pavone",
      "Ruth Pérez",
      "James Alberson, Jr.",
      "Carmen Rivera",
      "Valerie O'Halloran",
      "Ryan McIrvin",
      "Ed Prince",
      "Kim-Khánh Văn"
    ]

    sorted_names = sorted_people.map { |person| person["name"] }
    assert_equal expected_order, sorted_names
  end

  def test_sort_alphabetically_when_same_role_and_no_division
    people_same_role = [
      { "name" => "Person C", "positions" => ["council member"] },
      { "name" => "Person A", "positions" => ["council member"] },
      { "name" => "Person B", "positions" => ["council member"] }
    ]

    sorted_people = Core::PersonManager::Utils.sort_people(people_same_role, @positions_config)
    expected_order = ["Person A", "Person B", "Person C"]
    sorted_names = sorted_people.map { |person| person["name"] }
    assert_equal expected_order, sorted_names
  end
end
