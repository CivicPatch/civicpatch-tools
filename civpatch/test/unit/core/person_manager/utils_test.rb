# frozen_string_literal: true

require "test_helper"
require "core/person_manager/utils"
require "core/path_helper"
require "core/city_manager"

class CorePersonManagerUtilsTest < Minitest::Test
  #
  # Role Normalization Tests
  # 
  def test_normalize_role_exact_match
    assert_equal ["Mayor"], Core::PersonManager::Utils.normalize_role("mayor_council", "mayor")
  end

  def test_normalize_role_multiple_roles
    assert_equal ["Mayor", "Council Member"], Core::PersonManager::Utils.normalize_role("mayor_council", "mayor, council member")
  end

  #
  # Division Normalization Tests
  #
  def test_normalize_division_exact_match
    assert_equal "At-large", Core::PersonManager::Utils.normalize_division("at-large")
    assert_equal "Ward", Core::PersonManager::Utils.normalize_division("ward")
  end

  def test_normalize_division_alias_match
    assert_equal "At-large", Core::PersonManager::Utils.normalize_division("citywide")
    assert_equal "At-large", Core::PersonManager::Utils.normalize_division("city wide")
    assert_equal "Zone", Core::PersonManager::Utils.normalize_division("zone")
    assert_equal "District", Core::PersonManager::Utils.normalize_division("district")
  end

  def test_normalize_division_with_number_word
    assert_equal "Ward 3", Core::PersonManager::Utils.normalize_division("ward three")
    assert_equal "Ward 2", Core::PersonManager::Utils.normalize_division("ward ii")
  end

  def test_normalize_division_returns_nil_for_blank
    assert_nil Core::PersonManager::Utils.normalize_division(nil)
    assert_nil Core::PersonManager::Utils.normalize_division("")
    assert_nil Core::PersonManager::Utils.normalize_division("   ")
  end

  def test_normalize_division_fallback
    assert_equal "Unknown", Core::PersonManager::Utils.normalize_division("unknown")
  end

  def test_sort_people_by_role_index
    # Mock Core::CityManager.roles to control role order
    government_type = "city"
    roles = [
      { "role" => "Mayor", "aliases" => [] },
      { "role" => "Council Member", "aliases" => ["Councilman", "Councilwoman"] },
      { "role" => "Clerk", "aliases" => [] }
    ]
    Core::CityManager.stub :roles, roles do
      people = [
        { "name" => "Charlie", "roles" => ["Clerk"], "divisions" => ["District 2"] },
        { "name" => "Alice", "roles" => ["Mayor"], "divisions" => ["District 1"] },
        { "name" => "Bob", "roles" => ["Council Member"], "divisions" => ["District 1"] },
        { "name" => "Eve", "roles" => ["Unknown Role"], "divisions" => ["District 3"] }
      ]
      sorted = Core::PersonManager::Utils.sort_people(government_type, people)
      assert_equal ["Alice", "Bob", "Charlie", "Eve"], sorted.map { |p| p["name"] }
    end
  end

  def test_sort_people_by_division_and_name
    government_type = "city"
    roles = [
      { "role" => "Council Member", "aliases" => [] }
    ]
    Core::CityManager.stub :roles, roles do
      people = [
        { "name" => "Zara", "roles" => ["Council Member"], "divisions" => ["District B"] },
        { "name" => "Anna", "roles" => ["Council Member"], "divisions" => ["District A"] },
        { "name" => "Mike", "roles" => ["Council Member"], "divisions" => ["District A"] }
      ]
      sorted = Core::PersonManager::Utils.sort_people(government_type, people)
      # Anna and Mike have same role and division, so sort by name
      assert_equal ["Anna", "Mike", "Zara"], sorted.map { |p| p["name"] }
    end
  end

  def test_sort_people_with_missing_fields
    government_type = "city"
    roles = [
      { "role" => "Mayor", "aliases" => [] }
    ]
    Core::CityManager.stub :roles, roles do
      people = [
        { "name" => "NoRole", "divisions" => ["District 1"] },
        { "name" => "NoDivision", "roles" => ["Mayor"] },
        { "roles" => ["Mayor"], "divisions" => ["District 2"] }
      ]
      sorted = Core::PersonManager::Utils.sort_people(government_type, people)
      # "NoDivision" and the nameless person have role "Mayor", so come first, sorted by division then name (nil name last)
      assert_equal ["NoDivision", nil, "NoRole"], sorted.map { |p| p["name"] }
    end
  end

  def test_sort_people_unknown_role_sorts_last
    government_type = "city"
    roles = [
      { "role" => "Mayor", "aliases" => [] }
    ]
    Core::CityManager.stub :roles, roles do
      people = [
        { "name" => "Known", "roles" => ["Mayor"], "divisions" => ["D1"] },
        { "name" => "Unknown", "roles" => ["Alien"], "divisions" => ["D2"] }
      ]
      sorted = Core::PersonManager::Utils.sort_people(government_type, people)
      assert_equal ["Known", "Unknown"], sorted.map { |p| p["name"] }
    end
  end
end
