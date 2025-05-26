# frozen_string_literal: true

module GitHub
  class MunicipalityOfficials
    # TODO: add this back under main comment
    ## Action Items
    #     - [ ] Review & Merge this PR
    #       - [ ] (Optional) Make updates to people.yml if needed
    #       - [ ] (Optional) Make updates to config.yml if needed
    #       - [ ] (Optional) Leave a comment if the data cannot be fixed by making updates to the YAML files
    #
    #
    def self.generate_pull_request_body(context, has_github_env, current_branch)
      if has_github_env
        state = context[:state]
        geoid = context[:municipality_entry]["geoid"]

        city_path = Core::PathHelper.get_data_city_path(state, geoid)
        data_relative_path = city_path[city_path.rindex("data/#{state}")..]
        data_source_relative_path = city_path[city_path.rindex("data_source/#{state}")..]
        config_link = "https://github.com/CivicPatch/open-data/edit/#{current_branch}/#{data_source_relative_path}/config.yml"
        people_link = "https://github.com/CivicPatch/open-data/edit/#{current_branch}/#{data_relative_path}/people.yml"

        <<~PR_BODY
          PR opened by the Municipal Officials - Scrape workflow.
          * people.yml - Make changes [here](#{people_link}) and validation workflows will re-run.
          * config.yml - Make changes [here](#{config_link}) and the entire pipeline will re-run
          (note: if you want the whole pipeline to re-run, do not make changes to people.yml)
        PR_BODY
      else
        "PR opened by the Municipal Officials - Scrape workflow."
      end
    end

    def self.people_list(context, people) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/PerceivedComplexity
      municipality_name = context[:municipality_entry]["name"]
      state = context[:state]
      sources = people.map { |person| person["sources"] }.flatten.uniq.join("\n")

      <<~MARKDOWN
        # #{municipality_name}, #{state.upcase}
        ## Sources
        #{sources}
        ## People
        | **Name**  | **Positions**     | **Email**     | **Phone**     | **Website**   | **Term Dates** | **Image**     |
        |-----------|-------------------|---------------|---------------|---------------|----------------|---------------|
        #{people.map do |person|
          image = person["cdn_image"]
          email = person["email"]
          phone = person["phone_number"]
          website = person["website"]
          start_term_date = person["start_date"].present? ? person["start_date"] : "N/A"
          end_term_date = person["end_date"].present? ? person["end_date"] : "N/A"
          term_date_markdown = "#{start_term_date} - #{end_term_date}"

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

    def self.review_comment(merged_people, contested_people, missing_people, agreement_score)
      missing_people_table = to_missing_people_table(missing_people)
      disagreement_table = to_disagreement_table(contested_people, merged_people)
      <<~MARKDOWN
        ## Agreement Score: #{agreement_score}
        ---
        ### Missing People
        #{missing_people_table || "N/A"}
        ### Disagreements
        #{disagreement_table || "N/A"}
      MARKDOWN
    end

    def self.to_missing_people_table(missing_people)
      return "" if missing_people.nil? || missing_people.empty?

      headers = ["Name", "Missing From"]
      table = []
      markdown = "### Missing People\n\n"

      missing_people.each do |name, sources|
        table << [name, sources.join(", ")]
      end

      markdown += "| #{headers.join(" | ")} |"
      separator_line = "| #{headers.map { |header| "-" * header.length }.join(" | ")} |"
      markdown += "\n#{separator_line}"
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |"
      end

      markdown
    end

    def self.to_disagreement_table(contested_people, merged_people)
      table = ""
      contested_people.each do |name, fields|
        merged_person = merged_people.find { |person| person["name"] == name }
        contested_people_markdown = GitHub::MunicipalityOfficials.to_disagreement_table_person(fields,
                                                                                               merged_person)
        table += "### #{name}\n\n"
        table += contested_people_markdown
        table += "\n\n---\n\n" # Add a separator between each person's table
      end

      table
    end

    def self.to_disagreement_table_person(contested_fields, merged_person)
      # Prepare source headers
      source_names = contested_fields.map { |_, field_data| field_data[:values].keys }.flatten.uniq
      headers = ["Field", "Disagreement Score"] + source_names
      table = []

      contested_fields.each do |field, field_data|
        row = [
          field.to_s.split("_").map(&:capitalize).join(" "),
          field_data[:disagreement_score].round(2)
        ]

        merged_value = merged_person[field]

        source_names.each do |source_name|
          value = field_data[:values][source_name]
          display_value = format_display_value(value, merged_value)
          formatted_display_value = if values_match?(value, merged_value)
                                      display_value
                                    else
                                      "**#{display_value}** ❌"
                                    end

          row << formatted_display_value
        end

        table << row
      end

      # Build markdown string
      markdown = "| #{headers.join(" | ")} |"
      separator_line = "| #{headers.map { |header| "-" * header.length }.join(" | ")} |"
      markdown += "\n#{separator_line}"
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |"
      end

      markdown
    end

    def self.values_match?(source_value, merged_value)
      return true if source_value.nil? # Nil values don't contribute anything

      source_array = Array(source_value).compact
      merged_array = Array(merged_value).compact

      return false if source_array.empty?

      # Scalar comparison
      return source_array.first == merged_array.first if source_array.size == 1 && merged_array.size == 1

      # Check if any source values contributed
      (source_array & merged_array).any?
    end

    def self.format_display_value(source_value, merged_value)
      return "(missing)" if source_value.nil? || (source_value.is_a?(Array) && source_value.empty?)

      if source_value.is_a?(Array)
        source_value.map do |val|
          merged_array = Array(merged_value).compact
          merged_array.include?(val) ? val : "**#{val}**"
        end.join(", ")
      else
        source_value.to_s
      end
    end

    # def self.generate_suggest_edit_markdown(
    #  merged_people, suggest_edit_details, missing_people, contested_people
    # )
    #  return "" if suggest_edit_details.nil?

    #  action_item_summary = generate_readable_updates_needed_list(
    #    merged_people, missing_people, contested_people
    #  )
    #  return "" unless action_item_summary.present?

    #  case suggest_edit_details[:type]
    #  when "email"
    #    email = suggest_edit_details[:data]
    #    source_url = suggest_edit_details[:source_url]
    #    <<~MARKDOWN
    #      - [ ] (Optional) Notify the state source maintaners of any changes as needed
    #          - [ ] Verify the state source data at [#{source_url}](#{source_url})
    #          - [ ] Email the maintainer(s) at [#{email}](mailto:#{email})
    #      #{action_item_summary}
    #    MARKDOWN
    #  when "url"
    #    <<~MARKDOWN
    #      - [ ] (Optional) Update the state source directory: #{suggest_edit_details[:data]}
    #      #{action_item_summary}
    #    MARKDOWN
    #  end
    # end

    # def self.generate_readable_updates_needed_list(merged_people, missing_people, contested_people)
    #  source_to_update = "state_source"
    #  not_in_office_list = []
    #  updates_needed_markdown = ""

    #  missing_people.each_key do |name|
    #    not_in_office_list << name unless missing_people[name].include?(source_to_update)
    #  end
    #  not_in_office_markdown = not_in_office_list.map { |name| "- #{name}" }.join("\n")

    #  if not_in_office_markdown.present?
    #    not_in_office_markdown = "The following officials are no longer in office:\n#{not_in_office_markdown}"
    #  end

    #  contested_people.each do |contested_person_name, contested_fields|
    #    merged_person = merged_people.find { |person| person["name"] == contested_person_name }

    #    next if merged_person.nil?

    #    updates_needed = get_updates_needed(source_to_update, merged_person, contested_fields)

    #    next unless updates_needed.present? && updates_needed.count.positive?

    #    updates_needed_markdown += "**#{contested_person_name}**\n"
    #    updates_needed.each do |update_needed|
    #      updates_needed_markdown += "- #{update_needed}\n"
    #    end
    #  end

    #  if updates_needed_markdown.present?
    #    updates_needed_markdown = "The following officials may need updates to their records:\n#{
    #      updates_needed_markdown
    #    }"
    #  end

    #  if not_in_office_markdown.present? || updates_needed_markdown.present?
    #    <<~MARKDOWN
    #      <blockquote><details>
    #      <summary>Click to expand</summary>

    #      ```md
    #      #{[not_in_office_markdown, updates_needed_markdown].compact.join("\n")}
    #      ```
    #      </details></blockquote>
    #    MARKDOWN
    #  else
    #    ""
    #  end
    # end
  end
end
