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
require "core/people_manager"
require_relative "../core/context_manager"

namespace :github_pipeline do
  desc "Generate pull request details"
  task :pr_details, [:state, :geoid, :current_branch] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]
    current_branch = args[:current_branch]
    has_github_env = ENV["GITHUB_ENV"].present?

    context = Core::ContextManager.get_context(state, geoid)
    municipality_name = context[:municipality_entry]["name"]

    comment = GitHub::MunicipalityOfficials.generate_pull_request_body(context, has_github_env, current_branch)

    title = "Add municipal officials for #{municipality_name}, #{state}"
    commit_message = "Add municipal officials for #{municipality_name}, #{state}"

    data = {
      "commit_message" => commit_message,
      "pr_title" => title.gsub(/\n/, '\n'),
      "pr_body" => comment.gsub(/\n/, '\n')
    }
    puts JSON.generate(data)
  end

  desc "Generate comment for a pull request"
  task :generate_comment, [:state, :geoid] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]

    context = Core::ContextManager.get_context(state, geoid)

    people = Core::PeopleManager.get_people(state, geoid)
    people_comment = GitHub::MunicipalityOfficials.people_list(context, people)

    data = {
      "comment" => people_comment.gsub(/\n/, '\n')
    }

    puts JSON.generate(data)
  end

  desc "Generate review for a pull request"
  task :generate_review, [:state, :geoid] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]

    context = Core::ContextManager.get_context(state, geoid)

    merged_people = Core::PeopleManager.get_people(state, geoid)
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
