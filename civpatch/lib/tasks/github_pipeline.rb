# frozen_string_literal: true

# This file contains rake tasks and supporting code for the GitHub pipeline.
# It handles:
# - Generating PR comments for city directories
# - Updating city directories with new data
# - Managing the GitHub repository
#
# Main tasks:
# - github_pipeline:get_pr_comment[state,geoid,branch_name]# Generate markdown for PR

require "github/municipality_officials"
require "resolvers/people_resolver"
require_relative "../core/context_manager"

namespace :github_pipeline do
  desc "Generate comment for a pull request"
  task :generate_comment, [:state, :geoid] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]

    context = Core::ContextManager.get_context(state, geoid)

    people = Resolvers::PeopleResolver.merge_people_across_sources(context)
    people_comment = GitHub::MunicipalityOfficials.people_list(context, people)

    puts people_comment
  end

  desc "Generate review for a pull request"
  task :generate_review, [:state, :geoid] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]

    context = Core::ContextManager.get_context(state, geoid)

    merged_people = Resolvers::PeopleResolver.merge_people_across_sources(context)
    comparison = Resolvers::PeopleResolver.compare_people_across_sources(context)

    comment = GitHub::MunicipalityOfficials.review_comment(merged_people,
                                                           comparison[:contested_people],
                                                           comparison[:missing_people],
                                                           comparison[:agreement_score])
    review = {
      "score" => comparison[:agreement_score],
      "comment" => comment.gsub(/\n/, '\n')
    }
    puts JSON.generate(review)
  end
end
