# frozen_string_literal: true

require "test_helper"
require_relative "../../lib/scrapers/standard"

class StandardTest < Minitest::Test
  def test_determine_positions_with_simple_position
    positions = ["Mayor"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    assert_equal 1, result.size
    assert_equal "Mayor", result.first["name"]
    assert_equal start_date, result.first["start_date"]
    assert_equal end_date, result.first["end_date"]
  end

  def test_determine_positions_with_passthrough
    positions = ["City Manager"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    assert_equal 1, result.size
    assert_equal "City Manager", result.first["name"]
    assert_equal start_date, result.first["start_date"]
    assert_equal end_date, result.first["end_date"]
  end

  def test_determine_positions_with_multiple_positions
    positions = ["Mayor", "Council Member"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    assert_equal 2, result.size
    assert_includes result.map { |p| p["name"] }, "Mayor"
    assert_includes result.map { |p| p["name"] }, "Council Member"
  end

  def test_determine_positions_with_empty_input
    result = Scrapers::Standard.determine_positions([], nil, nil)

    assert_empty result
  end

  def test_determine_positions_with_unknown_position
    positions = ["Unknown Role"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    assert_equal 1, result.size
    assert_equal "Unknown Role", result.first["name"] # Should preserve unknown positions
  end

  def test_determine_positions_with_nil_dates
    positions = ["Mayor"]

    result = Scrapers::Standard.determine_positions(positions, nil, nil)

    assert_equal 1, result.size
    assert_nil result.first["start_date"]
    assert_nil result.first["end_date"]
  end

  def test_determine_positions_preserves_position_order
    positions = ["Council Member", "Mayor", "City Manager"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    expected_order = ["Council Member", "Mayor", "City Manager"]
    actual_order = result.map { |p| p["name"] }

    assert_equal expected_order, actual_order
  end

  def test_determine_positions_with_implied_roles
    positions = ["Ward 3"]
    start_date = "2024-01-01"
    end_date = "2028-01-01"

    result = Scrapers::Standard.determine_positions(positions, start_date, end_date)

    assert_equal 2, result.size
    assert_includes result.map { |p| p["name"] }, "Council Member"
    assert_includes result.map { |p| p["name"] }, "Ward 3"
  end

  def test_determine_positions_with_aliases
    positions = ["CouncilMember"]

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    assert_equal 1, result.size
    assert_includes result.map { |p| p["name"] }, "Council Member"
  end

  def test_determine_positions_formatted_positions
    positions = ["Ward #5"]

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    assert_equal 1, result.size
    assert_includes result.map { |p| p["name"] }, "Ward 5"
  end

  def test_exact_match_positions_from_mayor_council
    # Test for exact matches from the mayor_council config
    positions = ["council president"] # Exactly as in config

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    assert_equal 1, result.size
    assert_equal "council president", result.first["name"]
  end

  def test_exact_match_with_different_case
    # Test for case-insensitive exact matches
    positions = ["Council President"] # Different case than config

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    assert_equal 1, result.size
    assert_equal "council president", result.first["name"]
  end

  def test_division_handling_with_exact_match_priority
    # Tests that exact matches are prioritized over division splitting
    positions = ["council president ward 3"] # Should NOT be split if exact match exists

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    # Should preserve council president as one role, add ward 3 as division
    assert_equal 2, result.size
    assert_includes result.map { |p| p["name"] }, "council president"
    assert_includes result.map { |p| p["name"] }, "ward 3"
  end

  def test_preserve_exact_match_for_compound_roles
    # Test for preserving specific compound roles from config
    positions = ["president board of aldermen"] # Exact match in aldermen config

    result = Scrapers::Standard.determine_positions(positions, nil, nil)
    assert_equal 1, result.size
    assert_equal "president board of aldermen", result.first["name"]
  end
end
