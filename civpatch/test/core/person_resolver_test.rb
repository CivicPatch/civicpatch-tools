# frozen_string_literal: true

# test/core/person_resolver_test.rb
require "test_helper"
require "minitest/autorun"
require "resolvers/person_resolver" # Adjust path as necessary

class PersonResolverTest < Minitest::Test
  def setup
    # Test Data
    @person1 = { "name" => "Jane Doe", "email" => "jane.doe@example.com", "website" => "https://jane.example.com" }
    @person2 = { "name" => "John Doe", "email" => "john.doe@example.com", "website" => "https://john.example.com" }
    @person3 = { "name" => "Jane Smith", "email" => "jane.smith@example.com", "website" => "https://smith.example.com" }
    @person1_alt_case = { "name" => "jane doe", "email" => "JANE.DOE@EXAMPLE.COM", "website" => "https://JANE.example.com" }
    @person1_substring = { "name" => "Jane" } # For substring matching
    @person1_other_name = { "name" => "Janie Doe" } # Name in other_names
    # Different name, same email/last name
    @person_weak_match = { "name" => "J. Doe", "email" => "jane.doe@example.com" }
    # Same website/last name
    @person_weak_match_web = { "name" => "J. Doe", "email" => "diff@ex.com", "website" => "https://jane.example.com" }
    @person_no_email = { "name" => "No Email Doe", "website" => "https://nodoe.com", "email" => nil }
    @person_no_website = { "name" => "No Web Doe", "email" => "noweb@example.com", "website" => nil }
    @person_nil_fields = { "name" => "Nil Doe", "email" => nil, "website" => nil }
    @person_long_name = { "name" => "Jane Elizabeth Doe" }
    @person_eduardo = { "name" => "Eduardo Morales" }
    @person_victoria = { "name" => "Victoria Doyle" }

    @people = [@person1, @person2, @person3, @person_long_name, @person_eduardo, @person_victoria]

    # Config uses the primary name as the key
    @people_config = {
      "Jane Doe" => { "other_names" => ["Janie Doe", "J. Doe"] },
      "John Doe" => { "other_names" => [] },
      "Jane Smith" => { "other_names" => ["J. Smith"] },
      "Jane Elizabeth Doe" => { "other_names" => [] }, # Example for substring test
      "Eduardo Morales" => { "other_names" => ["Eddy Morales"] },
      "Victoria Doyle" => { "other_names" => [] }
    }
    @people_config_missing_other_names = {
      "Jane Doe" => {}, # Missing other_names key
      "John Doe" => { "other_names" => [] }
    }

    # Deep copy for mutation testing in find_existing_person tests
    @config_for_update = Marshal.load(Marshal.dump(@people_config))
  end

  # --- Helper Method Tests (.same_...?) ---

  def test_same_email_matching
    person1_same_email = @person1.dup # Ensure email field exists and matches
    assert Resolvers::PersonResolver.same_email?(@person1, person1_same_email)
  end

  def test_same_email_matching_case_insensitive
    assert Resolvers::PersonResolver.same_email?(@person1, @person1_alt_case)
  end

  def test_same_email_different
    refute Resolvers::PersonResolver.same_email?(@person1, @person2)
  end

  def test_same_email_one_nil
    # This will raise NoMethodError if not handled, test assumes it should be false
    refute Resolvers::PersonResolver.same_email?(@person1, @person_no_email)
  end

  def test_same_email_both_nil
    # This will raise NoMethodError if not handled, test assumes it should be false
    refute Resolvers::PersonResolver.same_email?(@person_nil_fields, @person_nil_fields)
  end

  def test_same_website_matching
    person1_same_website = @person1.dup
    assert Resolvers::PersonResolver.same_website?(@person1, person1_same_website)
  end

  def test_same_website_matching_case_insensitive
    assert Resolvers::PersonResolver.same_website?(@person1, @person1_alt_case)
  end

  def test_same_website_different
    refute Resolvers::PersonResolver.same_website?(@person1, @person2)
  end

  def test_same_website_one_nil
    # This will raise NoMethodError if not handled, test assumes it should be false
    refute Resolvers::PersonResolver.same_website?(@person1, @person_no_website)
  end

  def test_same_website_both_nil
    # This will raise NoMethodError if not handled, test assumes it should be false
    refute Resolvers::PersonResolver.same_website?(@person_nil_fields, @person_nil_fields)
  end

  # --- .name_in_config? Test (Updated Signature) ---

  def test_name_in_config_other_names_match
    config_entry = @people_config["Jane Doe"]
    assert Resolvers::PersonResolver.name_in_config?({ "Jane Doe" => config_entry }, "Janie Doe")
  end

  def test_name_in_config_no_match
    config_entry = @people_config["Jane Doe"]
    refute Resolvers::PersonResolver.name_in_config?({ "Jane Doe" => config_entry }, "John Doe")
  end

  def test_name_in_config_missing_other_names_key
    config_entry = @people_config_missing_other_names["Jane Doe"]
    # This should not raise an error and return false
    refute Resolvers::PersonResolver.name_in_config?({ "Jane Doe" => config_entry }, "Janie Doe")
  end

  def test_name_in_config_nil_config_entry
    # This should not raise an error and return false
    refute Resolvers::PersonResolver.name_in_config?(nil, "Janie Doe")
  end

  # --- Tests for .find_by_name (Previously match_by_name) ---

  def test_find_by_name_exact_match
    needle_name = "Jane Doe"
    assert_equal @person1, Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  def test_find_by_name_substring_match_needle_in_haystack
    needle_name = "Jane" # Substring of "Jane Doe" and "Jane Elizabeth Doe"
    # It should return nil -- needs a last name to match
    assert_nil Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  def test_find_by_name_substring_match_haystack_in_needle
    needle_name = "Dr. Jane Doe" # Contains "Jane Doe"
    assert_equal @person1, Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  def test_find_by_name_other_name_match
    needle_name = "Janie Doe" # In other_names for "Jane Doe"
    assert_equal @person1, Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  def test_find_by_name_no_match
    needle_name = "Unknown Person"
    assert_nil Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  def test_find_by_name_blank_config
    needle_name = "Lily Evans"
    assert_nil Resolvers::PersonResolver.find_by_name({}, @people, needle_name)
    assert_nil Resolvers::PersonResolver.find_by_name(nil, @people, needle_name)
  end

  def test_find_by_name_config_present_but_no_other_names_match
    needle_name = "Janet Doe" # Similar name, but not in other_names
    # Should not match based on name_in_config? alone if substring fails
    refute Resolvers::PersonResolver.name_in_config?({ "Jane Doe" => @people_config["Jane Doe"] }, needle_name)
    assert_nil Resolvers::PersonResolver.find_by_name(@people_config, @people, needle_name)
  end

  # --- .match_by_weak_ties Tests ---

  def test_match_by_weak_ties_last_name_and_email
    # Uses @person_weak_match which has different name but same last name/email as @person1
    assert_equal @person1, Resolvers::PersonResolver.match_by_weak_ties(@people, @person_weak_match)
  end

  def test_match_by_weak_ties_last_name_and_website
    # Uses @person_weak_match_web which has different name/email but same last name/website as @person1
    assert_equal @person1, Resolvers::PersonResolver.match_by_weak_ties(@people, @person_weak_match_web)
  end

  def test_match_by_weak_ties_only_last_name
    needle = { "name" => "J. Doe", "email" => "diff@example.com", "website" => "diff.com" }
    assert_nil Resolvers::PersonResolver.match_by_weak_ties(@people, needle)
  end

  def test_match_by_weak_ties_email_and_last_name
    needle = { "name" => "J. Doe", "email" => "jane.doe@example.com", "website" => "https://jane.example.com" }
    assert_equal @person1, Resolvers::PersonResolver.match_by_weak_ties(@people, needle)
  end

  def test_match_by_weak_ties_different_last_names
    needle = { "name" => "J. Smith", "email" => "jane.doe@example.com", "website" => "https://jane.example.com" }
    assert_nil Resolvers::PersonResolver.match_by_weak_ties(@people, needle)
  end

  def test_match_by_weak_ties_handles_nil_in_needle
    # Should not match anything as email/website are nil
    assert_nil Resolvers::PersonResolver.match_by_weak_ties(@people, @person_nil_fields)
  end

  def test_match_by_weak_ties_handles_nil_in_haystack
    haystack = [@person_nil_fields, @person1]
    needle = { "name" => "Jane Doe", "email" => "jane.doe@example.com", "website" => "https://jane.example.com" }
    # Should skip person_nil_fields gracefully and match person1
    assert_equal @person1, Resolvers::PersonResolver.match_by_weak_ties(haystack, needle)
  end

  # --- .find_existing_person Tests ---

  def test_find_existing_person_exact_name_match
    found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, @person1.dup)
    assert_equal @person1, found
    assert_equal @people_config, config # Config shouldn't change
  end

  def test_find_existing_person_other_name_match_updates_config
    found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, @person1_other_name)
    assert_equal @person1, found
    assert_includes config["Jane Doe"]["other_names"], "Janie Doe"
  end

  def test_find_existing_person_weak_match_updates_config_if_names_differ
    found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, @person_weak_match)
    assert_equal @person1, found
    assert_includes config["Jane Doe"]["other_names"], "J. Doe"
  end

  def test_find_existing_person_does_not_add_duplicate_other_names
    # First call adds the name via weak match
    _found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, @person_weak_match)
    assert_equal 1, config["Jane Doe"]["other_names"].count("J. Doe")
    # Second call (e.g., finding via other_name) should not add it again
    _found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, @person_weak_match)
    assert_equal 1, config["Jane Doe"]["other_names"].count("J. Doe")
  end

  def test_find_existing_person_weak_match_same_name_no_config_change
    # Find person2 via weak ties using its own data (should resolve to itself)
    person2_weak_match = @person2.dup
    original_config_copy = Marshal.load(Marshal.dump(@people_config))
    found, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, person2_weak_match)
    assert_equal @person2, found
    assert_equal original_config_copy, config # Config shouldn't change
  end

  def test_find_existing_person_no_match
    new_person_no_match = { "name" => "Unknown Person", "email" => "unknown@example.com" }
    found_person, config = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, new_person_no_match)
    assert_nil found_person
    assert_equal @config_for_update, config
  end

  def test_find_existing_person_matches_name_with_middle_initial
    # Needle has a middle initial, haystack does not
    needle = { "name" => "Victoria M. Doyle" }
    expected_person = @person_victoria # Should match the existing "Victoria Doyle"

    found, config_after = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, needle)

    assert_equal expected_person, found,
                 "Should find '#{expected_person["name"]}' when searching for '#{needle["name"]}'"
    assert config_after.key?(expected_person["name"]), "Config should retain the key for '#{expected_person["name"]}'"
  end

  def test_find_existing_person_connects_other_name_to_primary_name
    needle = { "name" => "Eddy Morales" } # This name is in Eduardo's other_names
    expected_person = @person_eduardo
    config_before = Marshal.load(Marshal.dump(@config_for_update))

    found, config_after = Resolvers::PersonResolver.find_existing_person(@config_for_update, @people, needle)

    assert_equal expected_person, found, "Should find Eduardo Morales using the other name 'Eddy Morales'"
    # Ensure the config wasn't mutated unnecessarily (Eddy was already there)
    assert_equal config_before["Eduardo Morales"], config_after["Eduardo Morales"],
                 "Config for Eduardo Morales should not change when found via existing other_name"
  end
end
