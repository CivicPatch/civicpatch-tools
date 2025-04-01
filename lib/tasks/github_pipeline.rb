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
      #{city_directory["people"].map { |person| person["sources"].map { |source| source["url"] }.join("\n") }.join("\n")}
      ## People
      #{city_directory["people"].map do |person|
        simple_person = Utils.format_simple(person)
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

  task :validate_city_directory, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    city_directory_to_validate = CityScrape::CityManager.get_city_directory(state, city_entry)

    validation_results = Validators::CityDirectory.validate_directory(state, gnis, city_directory_to_validate["people"])
    approve = validation_results[:missing].empty? &&
              validation_results[:extra].empty? &&
              validation_results[:different].empty?
    approve_reasons = []

    if validation_results[:missing].count.positive?
      approve_reasons << "Missing people in city directory: #{validation_results[:missing].count}"
    end
    if validation_results[:extra].count.positive?
      approve_reasons << "Found more people than expected: #{validation_results[:extra].count}"
    end
    if validation_results[:different].count.positive?
      approve_reasons << "Different people found in different roles than expected: #{validation_results[:different].count}"
    end

    approve_reasons_markdown = Validators::CityDirectory.approve_reasons_to_markdown(approve, approve_reasons)
    diff_markdown = Validators::CityDirectory.diff_to_markdown(validation_results)

    response = { "approve" => approve,
                 "comment" => [approve_reasons_markdown, diff_markdown].join("\n***\n") }

    puts response.to_json
  end
end
