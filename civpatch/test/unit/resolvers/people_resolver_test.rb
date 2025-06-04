require "minitest/autorun"
require_relative "../../../lib/resolvers/people_resolver"

module Resolvers
  class PeopleResolverTest < Minitest::Test
    def setup
      # Minimal config for testing
      @context = {
        config: {
          "people" => {}
        }
      }
    end

    def test_merge_people_across_sources_merges_fields
      # Stub resolve_sources to return two sources with overlapping people
      Resolvers::PeopleResolver.stub :resolve_sources, [
        {
          source_name: "openai",
          confidence_score: 0.7,
          people: [
            { "name" => "Jane Doe", "email" => "jane@a.com", "roles" => ["mayor"], "sources" => ["openai"] }
          ]
        },
        {
          source_name: "gemini",
          confidence_score: 0.7,
          people: [
            { "name" => "Jane Doe", "email" => "jane@b.com", "roles" => ["mayor"], "sources" => ["gemini"] }
          ]
        }
      ] do
        # Stub select_best_value to always pick the first value for simplicity
        Resolvers::PeopleResolver.stub :select_best_value, ->(field, values) { values.first[:value] } do
          merged = Resolvers::PeopleResolver.merge_people_across_sources(@context)
          assert_equal 1, merged.size
          jane = merged.first
          assert_equal "Jane Doe", jane["name"]
          assert_equal ["mayor"], jane["roles"]
          assert_includes jane["sources"], "openai"
          assert_includes jane["sources"], "gemini"
        end
      end
    end

    def test_merge_people_across_sources_skips_unique_people
      Resolvers::PeopleResolver.stub :resolve_sources, [
        {
          source_name: "openai",
          confidence_score: 0.7,
          people: [
            { "name" => "Unique Person", "email" => "unique@a.com", "roles" => ["council"], "sources" => ["openai"] }
          ]
        }
      ] do
        merged = Resolvers::PeopleResolver.merge_people_across_sources(@context)
        assert_empty merged
      end
    end
  end
end
