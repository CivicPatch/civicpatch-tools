# frozen_string_literal: true

# This file contains rake tasks and supporting code for the GitHub pipeline.
# It handles:
# - Generating PR comments for city directories
# - Updating city directories with new data
# - Managing the GitHub repository
#
# Main tasks:
# - github_pipeline:get_pr_comment[state,gnis,branch_name]# Generate markdown for PR

require "github/municipality_officials"
require "resolvers/people_resolver"
require_relative "../core/context_manager"

namespace :github_pipeline do
  desc "Get people.yml link for pull request"
  task :get_city_directory_link, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    city_entry = Core::StateManager.get_city_entry_by_gnis(state, gnis)
    city_path = PathHelper.get_data_city_path(state, city_entry["gnis"])
    relative_path = city_path[city_path.rindex("data/#{state}")..]

    directory_url = "https://github.com/CivicPatch/open-data/edit/#{branch_name}/#{relative_path}/people.yml"
    puts directory_url
  end

  desc "Get config.yml link for pull request"
  task :get_config_link, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    city_entry = Core::StateManager.get_city_entry_by_gnis(state, gnis)
    city_path = PathHelper.get_data_source_city_path(state, city_entry["gnis"])
    relative_path = city_path[city_path.rindex("data_source/#{state}")..]

    config_url = "https://github.com/CivicPatch/open-data/edit/#{branch_name}/#{relative_path}/config.yml"
    puts config_url
  end

  desc "Generate PR comment data for city people"
  task :generate_pr_data, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    context = Core::ContextManager.get_context(state, gnis)

    contested_people, missing_people, merged_people, agreement_score = generate_comparison(context)
    people_list_section = GitHub::MunicipalityOfficials.generate_people_list_markdown(context, merged_people,
                                                                                      missing_people, contested_people)
    disagreements_section = generate_disagreements_section(merged_people, contested_people, agreement_score)

    data = {
      "approve" => disagreements_section["approve"],
      "comment" => [people_list_section, disagreements_section["comment"]]
           .join("\n\n***\n\n").to_s.gsub(/\n/, '\n')
    }

    puts JSON.generate(data)
  end

  def self.generate_comparison(municipality_context)
    validation_results = Resolvers::PeopleResolver.resolve(municipality_context)

    compare_results = validation_results[:compare_results]
    contested_people = compare_results[:contested_people]
    missing_people = compare_results[:missing_people]
    agreement_score = compare_results[:agreement_score]

    merged_people = validation_results[:merged_sources]

    [contested_people, missing_people, merged_people, agreement_score]
  end

  def self.generate_disagreements_section(merged_people, contested_people, agreement_score)
    # Initialize the comment with the agreement score
    comment = "# Agreement Score: #{agreement_score}%\n\n---\n\n"

    # Iterate through each contested person and their contested fields
    contested_people.each do |name, fields|
      # Generate the markdown table for the contested person
      merged_person = merged_people.find { |person| person["name"] == name }
      contested_people_markdown = GitHub::MunicipalityOfficials.to_markdown_disagreement_table(fields, merged_person)

      # Add a header for each contested person and append the table
      comment += "### #{name}\n\n"
      comment += contested_people_markdown
      comment += "\n\n---\n\n" # Add a separator between each person's table
    end

    { "approve" => agreement_score >= 0.7,
      "comment" => comment }
  end
end
