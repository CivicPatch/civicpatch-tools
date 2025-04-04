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

    directory_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/#{relative_path}/directory.yml"
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

    markdown_content = <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Sources
      #{city_directory.map { |person| person["sources"].map { |source| source["url"] } }.flatten.uniq.join("\n")}
      ## People
      #{city_directory.map do |person|
        simple_person = Utils::DirectoryHelper.format_simple(person)
        image = simple_person["image"]
        email = simple_person["email"]
        phone = simple_person["phone_number"]
        website = simple_person["website"]

        position_markdown = <<~POSITION
          **Positions:** #{if simple_person["positions"].present?
                             simple_person["positions"]
                           else
                             "N/A"
                           end
                         }
        POSITION

        image_markdown = if image.present?
                           image_url = "#{base_image_url}/#{image}?raw=true"
                           <<~IMAGE
                             <img src='#{image_url}' width='150' />
                           IMAGE
                         else
                           "" # Ensure image_markdown is an empty string if no image is present
                         end

        email_markdown = if email.present?
                           <<~EMAIL
                             **Email:** #{email}
                           EMAIL
                         else
                           "**Email:** N/A"
                         end

        phone_markdown = if phone.present?
                           <<~PHONE
                             **Phone:** #{phone}
                           PHONE
                         else
                           "**Phone:** N/A"
                         end

        website_markdown = if website.present?
                             <<~WEBSITE
                               **Website:** [Link](#{website})
                             WEBSITE
                           else
                             "**Website:** N/A"
                           end
        <<~PERSON
          ********************************************************
          ### **Name:** #{person["name"]}
          #{position_markdown}
          #{email_markdown}
          #{phone_markdown}
          #{website_markdown}
          #{image_markdown}
        PERSON
      end.join("\n")}
    MARKDOWN

    puts markdown_content
  end

  task :validate_city_people, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    validation_results = Validators::CityPeople.validate_sources(state, gnis)
    puts "validation_results: #{validation_results.inspect}"
    contested_people = validation_results[:contested_people]
    score = validation_results[:agreement_score]
    contested_people_markdown = GitHub::CityPeople.to_markdown_table(contested_people)

    json = { "approve" => false,
             "score" => score,
             "comment" => [
               "## Agreement Score: #{score}",
               "---",
               contested_people_markdown
             ].join("\n\n") }.to_json
    puts json
  end
end
