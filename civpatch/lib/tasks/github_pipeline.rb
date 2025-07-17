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

    missing_divisions = missing_divisions(merged_people)

    fail_reasons = []

    score = comparison[:agreement_score]

    fail_reasons << "Expected: agreement score >= 70, Found: #{score}" if score < 70

    fail_reasons << "Expected: >= 5 people, Found: #{merged_people.length}" if merged_people.length < 5

    fail_reasons << "Found missing divisions:\n#{missing_divisions.join('\n')}" if missing_divisions.length > 0

    if comparison[:missing_people].length.positive?
      missing_people_names = comparison[:missing_people].map { |name, _sources| name }.join(", ")

      fail_reasons << "Found missing people: #{missing_people_names}"
    end

    comment = GitHub::MunicipalityOfficials.review_comment(merged_people,
                                                           comparison[:contested_people],
                                                           comparison[:missing_people],
                                                           comparison[:agreement_score],
                                                           fail_reasons)

    should_approve = fail_reasons.empty?

    review = {
      "score" => comparison[:agreement_score],
      "should_approve" => should_approve,
      "comment" => comment.gsub(/\n/, '\n')
    }
    puts JSON.generate(review)
  end
end

def self.missing_divisions(people)
  divisions = {} # { "district": { numbers: { 1: 1, 2: 2 } } }

  people.each do |person|
    next if person["divisions"].nil? || person["divisions"].empty?

    person["divisions"].each do |division|
      parts = division.split(" ")
      division_type = parts.first
      division_number = parts.last

      divisions[division_type] ||= { numbers: {} }
      divisions[division_type][:numbers][division_number] ||= 0
      divisions[division_type][:numbers][division_number] += 1
    end
  end

  # Collect division type and division numbers that:
  # * have a lower count than the other division numbers within the same division type
  # * are missing entirely
  # Ex: { "district", { numbers: { 1: 1, 2: 2 } } }}
  #   missing: "Expected: district 2 (2) division(s), Found: district 1 (1) divisions"
  # Ex: { "district", { numbers: { 1: 1, 3: 1 } } }}
  #  missing: "Expected: district 2 (1) division(s), Found: none"
  missing = []
  divisions.each do |division_type, division_data|
    max_division_number = division_data[:numbers].keys.map(&:to_i).max

    next if max_division_number.zero?

    expected_division_numbers = (1..max_division_number).to_a
    expected_count = division_data[:numbers].values.max

    expected_division_numbers.each do |division_number|
      if division_data[:numbers][division_number.to_s].nil?
        missing << "Expected: #{division_type} #{division_number} (#{expected_count}) division(s), Found: none"
      elsif division_data[:numbers][division_number.to_s] < expected_count
        missing << "Expected: #{division_type} #{division_number} (#{expected_count}}) division(s), Found: #{division_type} #{division_number} (#{division_data[:numbers][division_number]}) divisions"
      end
    end
  end

  missing
end
