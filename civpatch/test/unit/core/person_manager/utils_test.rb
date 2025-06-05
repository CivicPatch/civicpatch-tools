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
end
