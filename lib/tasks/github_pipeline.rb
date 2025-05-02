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

    municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, gnis)
    municipality_config = Core::ConfigManager.get_config(state, gnis)

    municipality_context = {
      state: state,
      municipality_entry: municipality_entry,
      config: municipality_config
    }

    contested_people, missing_people, merged_people, agreement_score = generate_comparison(municipality_context)
    people_list_comment = generate_people_list_comment(municipality_context, merged_people, missing_people,
                                                       contested_people)
    disagreements_section = generate_disagreements_section(merged_people, contested_people, agreement_score)

    data = {
      "approve" => disagreements_section["approve"],
      "comment" => [people_list_comment, disagreements_section["comment"]]
           .join("\n\n***\n\n").to_s.gsub(/\n/, '\n')
    }

    puts JSON.generate(data)
  end

  def self.generate_people_list_comment(municipality_context, merged_people, missing_people, contested_people)
    state = municipality_context[:state]
    city_entry = municipality_context[:municipality_entry]
    city = city_entry["name"]

    city_directory = Core::PeopleManager.get_people(state, city_entry["gnis"])

    suggest_edit_details = Scrapers::MunicipalityOfficials.get_suggest_edit_details(municipality_context)

    action_items = GitHub::CityPeople.generate_suggest_edit_markdown(merged_people, suggest_edit_details, missing_people,
                                                                     contested_people)

    missing_people_comment = GitHub::CityPeople.to_markdown_missing_people_table(missing_people)

    <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Action Items
       - [ ] Review & Merge this PR
         - [ ] (Optional) Make updates to people.yml if needed
         - [ ] (Optional) Make updates to config.yml if needed
         - [ ] (Optional) Leave a comment if the data cannot be fixed by making updates to the YAML files
       #{action_items}
      ## Missing People
      #{missing_people_comment.present? ? missing_people_comment : "N/A"}
      ## Sources
      #{city_directory.map { |person| person["sources"] }.flatten.compact.uniq.join("\n")}
      ## People
      | **Name**  | **Positions**     | **Email**     | **Phone**     | **Website**   | **Term Dates** | **Image**     |
      |-----------|-------------------|---------------|---------------|---------------|----------------|---------------|
      #{city_directory.map do |person|
        image = person["image"]
        email = person["email"]
        phone = person["phone_number"]
        website = person["website"]
        start_term_date = person["start_term_date"].present? ? person["start_term_date"] : "N/A"
        end_term_date = person["end_term_date"].present? ? person["end_term_date"] : "N/A"
        term_date = "#{start_term_date} - #{end_term_date}"

        position_markdown = if person["positions"].present?
                              person["positions"].join(", ")
                            else
                              "N/A"
                            end

        image_markdown = if image.present?
                           "![](#{image})"
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

        "**#{person["name"]}**| #{position_markdown} | #{email_markdown} | #{phone_markdown} | #{website_markdown} | #{term_date_markdown} | #{image_markdown}"
      end.join("\n")}
    MARKDOWN
  end

  def self.generate_comparison(municipality_context)
    validation_results = Validators::CityPeople.validate_sources(municipality_context)

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
      contested_people_markdown = GitHub::CityPeople.to_markdown_disagreement_table(fields, merged_person)

      # Add a header for each contested person and append the table
      comment += "### #{name}\n\n"
      comment += contested_people_markdown
      comment += "\n\n---\n\n" # Add a separator between each person's table
    end

    { "approve" => agreement_score >= 0.7,
      "comment" => comment }
  end
end
