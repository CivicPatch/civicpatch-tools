# frozen_string_literal: true

# This file contains rake tasks and supporting code for the GitHub pipeline.
# It handles:
# - Generating PR comments for city directories
# - Updating city directories with new data
# - Managing the GitHub repository
#
# Main tasks:
# - github_pipeline:get_pr_comment[state,gnis,branch_name]# Generate markdown for PR

namespace :github_pipeline do
  desc "Generate PR comment for city directory"
  task :get_pr_comment, [:state, :gnis, :branch_name] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    state_city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    city = state_city_entry["name"]
    city_path = CityScrape::CityManager.get_city_path(state, state_city_entry)
    relative_path = city_path[city_path.rindex("data/us")..]

    base_image_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/#{relative_path}"

    city_directory = CityScrape::CityManager.get_city_directory(state, state_city_entry)

    markdown_content = <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Sources
      #{city_directory["sources"].join("\n")}
      ## People
      #{city_directory["people"].map do |person|
        position_markdown = <<~POSITION
          **Position:** #{person["position"] || "N/A"}
        POSITION

        position_misc_markdown = <<~POSITION_MISC
          **Position Misc:** #{person["position_misc"] || "N/A"}
        POSITION_MISC

        image_markdown = if person["image"].present?
                           image_url = "#{base_image_url}/#{person["image"]}?raw=true"
                           <<~IMAGE
                             <img src='#{image_url}' width='150' />
                           IMAGE
                         else
                           "" # Ensure image_markdown is an empty string if no image is present
                         end

        email_markdown = if person["email"].present?
                           <<~EMAIL
                             **Email:** #{person["email"]}
                           EMAIL
                         else
                           "**Email:** N/A"
                         end

        phone_markdown = if person["phone_number"].present?
                           <<~PHONE
                             **Phone:** #{person["phone_number"]}
                           PHONE
                         else
                           "**Phone:** N/A"
                         end

        website_markdown = if person["website"].present?
                             <<~WEBSITE
                               **Website:** [Link](#{person["website"]})
                             WEBSITE
                           else
                             "**Website:** N/A"
                           end
        <<~PERSON
          ********************************************************
          ### **Name:** #{person["name"]}
          #{position_markdown}
          #{position_misc_markdown}
          #{email_markdown}
          #{phone_markdown}
          #{website_markdown}
          #{image_markdown}
        PERSON
      end.join("\n")}
    MARKDOWN

    puts markdown_content
  end
end
