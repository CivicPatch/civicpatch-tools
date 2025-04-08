# frozen_string_literal: true

# This file contains rake tasks and supporting code for the GitHub pipeline.
# It handles:
# - Generating PR comments for city directories
# - Updating city directories with new data
# - Managing the GitHub repository
#
# Main tasks:
# - github_pipeline:get_pr_comment[state,gnis,branch_name]# Generate markdown for PR

require_relative "../validators/city_people"
require_relative "../github/city_people"

namespace :github_pipeline do
  desc "Get GitHub City Directory Link"
  task :get_city_directory_link, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    relative_path = city_path[city_path.rindex("data/#{state}")..]

    directory_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/#{relative_path}/people.yml"
    puts directory_url
  end

  desc "Generate PR comment for city people"
  task :get_pr_comment, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    state_city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    city = state_city_entry["name"]
    city_path = CityScrape::CityManager.get_city_path(state, state_city_entry)
    relative_path = city_path[city_path.rindex("data/#{state}")..]

    base_image_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/#{relative_path}"

    city_directory = CityScrape::CityManager.get_city_directory(state, state_city_entry)

    puts city_directory.inspect

    markdown_content = <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Sources
      #{city_directory.map { |person| person["sources"] }.flatten.compact.uniq.join("\n")}
      ## People
      | **Name**             | **Positions**                          | **Email**                   | **Phone**         | **Website**                                           | **Image**                                                                                     |
      |----------------------|----------------------------------------|-----------------------------|-------------------|-----------------------------------------------------|-----------------------------------------------------------------------------------------------|
      #{city_directory.map do |person|
        image = person["image"]
        email = person["email"]
        phone = person["phone_number"]
        website = person["website"]

        position_markdown = if person["positions"].present?
                              person["positions"].join(", ")
                            else
                              "N/A"
                            end

        image_markdown = if image.present?
                           image_url = "#{base_image_url}/#{image}?raw=true"
                           "![](#{image_url})"
                         else
                           "N/A"
                         end

        email_markdown = if email.present?
                           email
                         else
                           "N/A"
                         end

        phone_markdown = if phone.present?
                           phone
                         else
                           "N/A"
                         end

        website_markdown = if website.present?
                             "[Link](#{website})"
                           else
                             "N/A"
                           end

        <<~PERSON
          | **#{person["name"]}**        | #{position_markdown}                        | #{email_markdown}               | #{phone_markdown}   | #{website_markdown}                                          | #{image_markdown}                                                                 |
        PERSON
      end.join("\n")}
    MARKDOWN

    puts markdown_content
  end

  task :validate_city_people, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    # Get the validation results
    validation_results = Validators::CityPeople.validate_sources(state, gnis)
    contested_people = validation_results[:compare_results][:contested_people]
    score = validation_results[:compare_results][:agreement_score]
    pretty_score = (score * 100).round(2)

    # Initialize the comment with the agreement score
    comment = "## Agreement Score: #{pretty_score}%\n\n---\n\n"

    # Iterate through each contested person and their contested fields
    contested_people.each do |name, fields|
      # Generate the markdown table for the contested person
      contested_people_markdown = GitHub::CityPeople.to_markdown_table(fields)

      # Add a header for each contested person and append the table
      comment += "### #{name}\n\n"
      comment += contested_people_markdown
      comment += "\n\n---\n\n" # Add a separator between each person's table
    end

    json = { "approve" => score >= 0.8,
             "score" => score,
             "comment" => comment }.to_json
    puts json
  end
end
