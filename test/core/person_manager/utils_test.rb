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
    positions = ["position #4"]
    normalized = Core::PersonManager::Utils.normalize_positions(positions, @positions_config)
    assert_equal ["council member", "position 4"], normalized
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

  def test_handles_positions_with_unknown_roles_by_placing_them_last
    positions = ["zookeeper", "mayor", "councilmember at-large"]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal ["mayor", "council member", "at-large", "zookeeper"], sorted
  end

  def test_handles_roles_with_missing_divisions
    positions = ["councilmember", "councilmember at-large", "councilmember seat"]
    sorted = Core::PersonManager::Utils.sort_positions(positions, @positions_config)

    assert_equal ["council member", "at-large", "seat"], sorted
  end
end
