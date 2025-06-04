require 'minitest/autorun'
require_relative '../../civpatch/lib/resolvers/people_resolver' # Adjust as needed
require_relative '../../civpatch/lib/core/city_manager' # Adjust as needed
require_relative '../../civpatch/lib/core/person_resolver' # Adjust as needed - assuming this is where individual person resolver is

# Mock constants if not already defined or to override for test
module Core
  class CityManager
    GOOGLE_CIVIC_HEAD_ROLE = 'headOfGovernment' unless const_defined?(:GOOGLE_CIVIC_HEAD_ROLE)
    # or some generic member role
    GOOGLE_CIVIC_MEMBER_ROLE = 'legislatorUpperBody' unless const_defined?(:GOOGLE_CIVIC_MEMBER_ROLE)
  end
end

module Resolvers
  module PeopleResolver
    # Ensure these are defined for the test if they are not loaded from elsewhere
    GOOGLE_CIVIC_DIVISIONS = %w[ward district] unless const_defined?(:GOOGLE_CIVIC_DIVISIONS)
    GOOGLE_CIVIC_MUNICIPALITY_LEVEL = 'locality' unless const_defined?(:GOOGLE_CIVIC_MUNICIPALITY_LEVEL)
    GOOGLE_CIVIC_SUB_MUNICIPALITY_LEVEL = 'subLocality1' unless const_defined?(:GOOGLE_CIVIC_SUB_MUNICIPALITY_LEVEL)
    unless const_defined?(:POSITION_DIVISIONS_TO_GOOGLE_CIVIC_DIVISIONS)
      POSITION_DIVISIONS_TO_GOOGLE_CIVIC_DIVISIONS = {
        'district' => 'council_district',
        'ward' => 'ward'
      }
    end
  end

  module Core # Assuming this is the namespace for the individual PersonResolver
    class PersonResolver
      # This will be stubbed, but defining it makes the require happier if it's a real class
    end
  end
end

class PeopleResolverIntegrationTest < Minitest::Test
  def setup
    @municipality_context = {
      state: 'tx',
      municipality_entry: { 'name' => 'testville' },
      government_type: 'Mayor-Council'
    }

    # Sample raw people data
    @jane_mayor_raw = { 'name' => 'Jane Mayor', 'positions' => ['Mayor'], 'email' => 'jane@testville.gov' }
    @john_council_raw = { 'name' => 'John Council', 'positions' => ['Council Member, District 1'],
                          'phone' => '555-0101' }
    @alice_chair_raw = { 'name' => 'Alice Chair', 'positions' => ['Council Chair, District 1'],
                         'url' => 'alice.testville.gov' }
    @bob_atlarge_raw = { 'name' => 'Bob AtLarge', 'positions' => ['Council Member At-Large, Seat 2'] }
    @carol_wardrep_raw = { 'name' => 'Carol Wardrep', 'positions' => ['Council Member, Ward B'] }

    @people_raw = [
      @jane_mayor_raw,
      @john_council_raw,
      @alice_chair_raw,
      @bob_atlarge_raw,
      @carol_wardrep_raw
    ]

    # Expected resolved individual person data (output of stubbed Resolvers::Core::PersonResolver.to_google_civic_person)
    @jane_mayor_resolved = { 'name' => 'Jane Mayor', 'emails' => ['jane@testville.gov'] }
    @john_council_resolved = { 'name' => 'John Council', 'phones' => ['555-0101'] }
    @alice_chair_resolved = { 'name' => 'Alice Chair', 'urls' => ['alice.testville.gov'] }
    @bob_atlarge_resolved = { 'name' => 'Bob AtLarge' }
    @carol_wardrep_resolved = { 'name' => 'Carol Wardrep' }
  end

  def test_integration_to_google_civic_people
    # --- Define Stubs ---
    # Stub for Core::CityManager.role_to_google_civic_role
    role_map_stub = lambda do |government_type, position_title|
      if government_type == @municipality_context[:government_type]
        if position_title.start_with?('Mayor')
          Core::CityManager::GOOGLE_CIVIC_HEAD_ROLE
        elsif position_title.start_with?('Council') # Covers Member, Chair, At-Large
          Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE
        else
          'unknownRole' # Fallback for unexpected titles in this test
        end
      else
        'unknownRoleFromOtherGovernmentType'
      end
    end

    # Stub for Resolvers::Core::PersonResolver.to_google_civic_person
    person_resolver_stub = lambda do |raw_person_data|
      case raw_person_data['name']
      when 'Jane Mayor' then @jane_mayor_resolved
      when 'John Council' then @john_council_resolved
      when 'Alice Chair' then @alice_chair_resolved
      when 'Bob AtLarge' then @bob_atlarge_resolved
      when 'Carol Wardrep' then @carol_wardrep_resolved
      else
        { 'name' => raw_person_data['name'], 'error' => 'unknown person in stub' }
      end
    end

    # --- Execute with Stubs ---
    Core::CityManager.stub :role_to_google_civic_role, role_map_stub do
      Resolvers::Core::PersonResolver.stub :to_google_civic_person, person_resolver_stub do
        @result = Resolvers::PeopleResolver.to_google_civic_people(@municipality_context, @people_raw)
      end
    end

    # --- Assertions ---
    assert_officials
    assert_offices
    assert_divisions
  end

  private

  def assert_officials
    assert_equal 5, @result['officials'].size
    expected_officials_names = [
      'Jane Mayor', 'John Council', 'Alice Chair', 'Bob AtLarge', 'Carol Wardrep'
    ]
    actual_officials_names = @result['officials'].map { |o| o['name'] }
    assert_equal expected_officials_names.sort, actual_officials_names.sort

    # Check if the correct resolved data is present
    assert_includes @result['officials'], @jane_mayor_resolved
    assert_includes @result['officials'], @john_council_resolved
    assert_includes @result['officials'], @alice_chair_resolved
    assert_includes @result['officials'], @bob_atlarge_resolved
    assert_includes @result['officials'], @carol_wardrep_resolved
  end

  def assert_offices
    # Expected OCD IDs that will be used as divisionIds in offices
    testville_ocdid = 'ocd-division/country:us/state:tx/place:testville'
    district1_ocdid = 'ocd-division/country:us/state:tx/place:testville/council_district:1'
    ward_b_ocdid    = 'ocd-division/country:us/state:tx/place:testville/ward:B'

    # 1. Mayor's Office (Head, Locality)
    # 2. Council Members' General Office (Member, Locality) - for Bob AtLarge
    # 3. District 1 Office (Member, SubLocality) - for John Council, Alice Chair
    # 4. Ward B Office (Member, SubLocality) - for Carol Wardrep
    assert_equal 4, @result['offices'].size, 'Incorrect number of offices created'

    # Office 1: Mayor (Jane Mayor, index 0)
    mayor_office = @result['offices'].find do |o|
      o['roles'].include?(Core::CityManager::GOOGLE_CIVIC_HEAD_ROLE) &&
        o['divisionId'] == testville_ocdid
    end
    refute_nil mayor_office, "Mayor's office not found"
    assert_equal [0], mayor_office['officialIndices'].sort
    assert_equal [Resolvers::PeopleResolver::GOOGLE_CIVIC_MUNICIPALITY_LEVEL], mayor_office['levels']
    assert_equal Core::CityManager::GOOGLE_CIVIC_HEAD_ROLE, mayor_office['name']

    # Office 2: Council General/At-Large (Bob AtLarge, index 3)
    # This office should exist because Bob AtLarge has no specific sub-locality division from his title.
    council_general_office = @result['offices'].find do |o|
      o['roles'].include?(Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE) &&
        o['divisionId'] == testville_ocdid &&
        o['name'] == Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE # Distinguish from Mayor's office
    end
    refute_nil council_general_office, 'General Council (at-large) office not found'
    # John (1), Alice (2), Bob (3), Carol (4) are all "Council Members" in role
    # The locality office for MEMBER_ROLE should include those whose *only* division is locality
    # John, Alice, Carol have sub-locality divisions, so they get their own offices for those.
    # Bob AtLarge is purely locality for his role.
    # The current logic creates a locality-level office for *each person* first, then sub-locality.
    # So, Jane (0) has her mayor locality office.
    # John (1), Alice (2), Bob (3), Carol (4) all get a locality office for their MEMBER_ROLE.
    # Let's find the one for Bob (index 3) that doesn't get folded into a more specific office.
    # The logic for "existing_office" means all Council Members will be grouped here initially.
    # The test will be more precise about this: Jane (0), John(1), Alice(2), Bob(3), Carol(4)
    # Mayor is Office 1.
    # All others are Council Members. They will share a locality-level office if their role is the same.
    # John (idx 1), Alice (idx 2), Bob (idx 3), Carol (idx 4) are all council members.
    assert_equal [1, 2, 3, 4], council_general_office['officialIndices'].sort,
                 'General council office has wrong members'
    assert_equal [Resolvers::PeopleResolver::GOOGLE_CIVIC_MUNICIPALITY_LEVEL], council_general_office['levels']

    # Office 3: District 1 (John Council, index 1; Alice Chair, index 2)
    district1_office = @result['offices'].find { |o| o['divisionId'] == district1_ocdid }
    refute_nil district1_office, 'District 1 office not found'
    assert_equal [1, 2], district1_office['officialIndices'].sort
    assert_equal [Resolvers::PeopleResolver::GOOGLE_CIVIC_SUB_MUNICIPALITY_LEVEL], district1_office['levels']
    assert_equal [Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE], district1_office['roles'],
                 'District 1 office has wrong roles'
    assert_equal district1_ocdid, district1_office['name'], 'District 1 office has wrong name'

    # Office 4: Ward B (Carol Wardrep, index 4)
    ward_b_office = @result['offices'].find { |o| o['divisionId'] == ward_b_ocdid }
    refute_nil ward_b_office, 'Ward B office not found'
    assert_equal [4], ward_b_office['officialIndices'].sort
    assert_equal [Resolvers::PeopleResolver::GOOGLE_CIVIC_SUB_MUNICIPALITY_LEVEL], ward_b_office['levels']
    assert_equal [Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE], ward_b_office['roles'], 'Ward B office has wrong roles'
    assert_equal ward_b_ocdid, ward_b_office['name'], 'Ward B office has wrong name'
  end

  def assert_divisions
    testville_ocdid = 'ocd-division/country:us/state:tx/place:testville'
    district1_ocdid = 'ocd-division/country:us/state:tx/place:testville/council_district:1'
    ward_b_ocdid    = 'ocd-division/country:us/state:tx/place:testville/ward:B'

    assert_equal 3, @result['divisions'].size, 'Incorrect number of divisions'

    # Division 1: Testville (Locality)
    testville_div_data = @result['divisions'][testville_ocdid]
    refute_nil testville_div_data, 'Testville division data not found'
    assert_equal 'Testville', testville_div_data['name'] # From to_ocdid_name
    # It should point to the indices of offices that use this divisionId
    # Office 1 (Mayor) and Office 2 (Council General) use testville_ocdid
    mayor_office_idx = @result['offices'].find_index do |o|
      o['roles'].include?(Core::CityManager::GOOGLE_CIVIC_HEAD_ROLE) && o['divisionId'] == testville_ocdid
    end
    council_general_office_idx = @result['offices'].find_index do |o|
      o['roles'].include?(Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE) && o['divisionId'] == testville_ocdid && o['name'] == Core::CityManager::GOOGLE_CIVIC_MEMBER_ROLE
    end
    expected_testville_office_indices = [mayor_office_idx, council_general_office_idx].compact.sort
    assert_equal expected_testville_office_indices, testville_div_data['officeIndices'].sort

    # Division 2: District 1
    district1_div_data = @result['divisions'][district1_ocdid]
    refute_nil district1_div_data, 'District 1 division data not found'
    assert_equal '1', district1_div_data['name'] # From to_ocdid_name
    district1_office_idx = @result['offices'].find_index { |o| o['divisionId'] == district1_ocdid }
    assert_equal [district1_office_idx].compact, district1_div_data['officeIndices']

    # Division 3: Ward B
    ward_b_div_data = @result['divisions'][ward_b_ocdid]
    refute_nil ward_b_div_data, 'Ward B division data not found'
    assert_equal 'B', ward_b_div_data['name'] # From to_ocdid_name
    ward_b_office_idx = @result['offices'].find_index { |o| o['divisionId'] == ward_b_ocdid }
    assert_equal [ward_b_office_idx].compact, ward_b_div_data['officeIndices']
  end
end
