# frozen_string_literal: true

require "utils/url_helper"
require "resolvers/person_resolver"

module Services
  module Shared
    class People
      def self.to_person(person, source)
        formatted_person = {
          "name" => person["name"],
          "sources" => [source]
        }

        formatted_person["images"] = data_point?(person["image"]) ? [person["image"]] : []
        formatted_person["roles"] = if person["roles"].is_a?(Array) && person["roles"].length.positive?
                                      person["roles"].select do |role|
                                        data_point?(role)
                                      end
                                    else
                                      []
                                    end
        formatted_person["divisions"] = if person["divisions"].is_a?(Array) && person["divisions"].length.positive?
                                          person["divisions"].select do |division|
                                            data_point?(division)
                                          end
                                        else
                                          []
                                        end
        formatted_person["phone_numbers"] =
          data_point?(person["phone_number"]) ? [person["phone_number"]] : []
        formatted_person["emails"] =
          data_point?(person["email"]) && valid_email?(person["email"]["data"]) ? [person["email"]] : []
        formatted_person["websites"] =
          if data_point?(person["website"]) && valid_website?(person["website"]["data"])
            [format_website_data_point(person["website"])]
          else
            []
          end
        formatted_person["start_dates"] =
          data_point?(person["start_date"]) ? [person["start_date"]] : []
        formatted_person["end_dates"] =
          data_point?(person["end_date"]) ? [person["end_date"]] : []

        data_points_with_source(formatted_person, source)
      end

      def self.merge_person(person, partial_person)
        merged = person.dup

        merged["roles"] = (Array(person["roles"]) + Array(partial_person["roles"]))
        merged["divisions"] = (Array(person["divisions"]) + Array(partial_person["divisions"]))
        merged["images"] = (Array(person["images"]) + Array(partial_person["images"]))
        merged["phone_numbers"] = (Array(person["phone_numbers"]) + Array(partial_person["phone_numbers"]))
        merged["emails"] = (Array(person["emails"]) + Array(partial_person["emails"]))
        merged["websites"] = (Array(person["websites"]) + Array(partial_person["websites"]))
        merged["start_dates"] = (Array(person["start_dates"]) + Array(partial_person["start_dates"]))
        merged["end_dates"] = (Array(person["end_dates"]) + Array(partial_person["end_dates"]))
        merged["sources"] = (Array(person["sources"]) + Array(partial_person["sources"]))

        merged
      end

      def self.collect_people(people_config, people, partial_people)
        updated_people_config = people_config.dup

        people_by_name = {}
        people.each do |person|
          canonical_name = Resolvers::PersonResolver.get_canonical_name(people_config, person)
          people_by_name[canonical_name] = person
        end

        partial_people.each do |partial_person|
          existing_person, updated_people_config = Resolvers::PersonResolver.find_existing_person(updated_people_config,
                                                                                                  people_by_name.values,
                                                                                                  partial_person)
          name = Resolvers::PersonResolver.get_canonical_name(updated_people_config, partial_person)
          people_by_name[name] = if existing_person.present?
                                   merge_person(existing_person, partial_person)
                                 else
                                   partial_person
                                 end
        end

        [people_by_name.values, updated_people_config]
      end

      def self.format_website_data_point(website_data_point)
        website_data_point["data"] = Utils::UrlHelper.format_url(website_data_point["data"])
        website_data_point
      end

      def self.valid_website?(url)
        parsed_uri = Addressable::URI.parse(url)
        has_path = parsed_uri.path.present? && parsed_uri.path != "/"
        url.present? && url.to_s.strip.present? && url.to_s.strip.start_with?("http") && has_path
      end

      def self.valid_email?(email)
        email.present? && email.to_s.strip.present? && email.to_s.strip.match?(URI::MailTo::EMAIL_REGEXP)
      end

      def self.data_points_with_source(person, source)
        %w[phone_numbers emails websites start_dates images end_dates].each do |data_point|
          next unless person[data_point].present?

          person[data_point].each do |data_point_item|
            data_point_item["source"] = Utils::UrlHelper.format_url(source)
          end
        end

        person
      end

      def self.data_point?(data_point)
        puts "DATA POINT: #{data_point}"
        return false unless data_point.is_a?(Hash)

        data_point["data"]&.present? &&
          data_point["data"].to_s.strip.present? &&
          data_point["data"] != "null"
      end

      def self.profile_data_points_present?(person)
        person["roles"].present? && person["roles"].count.positive? &&
          (
            person["websites"].present? && person["websites"].count.positive? ||
            contact_data_points_present?(person)
          )
      end

      # Returns true if the person has data points
      # for all of the following: phone_number, email, website
      def self.contact_data_points_present?(person)
        data_points_count = 0

        %w[phone_numbers emails websites].each do |data_point|
          data_points_count += 1 if person[data_point].present? && person[data_point].count.positive?
        end

        data_points_count >= 1
      end

      def self.all_contact_data_points_present?(person)
        %w[phone_numbers emails websites].all? do |data_point|
          person[data_point].present? && person[data_point].count.positive?
        end
      end

      def self.pick_best_data_point(data_points)
        return nil if data_points.blank?
        return data_points.first if data_points.count == 1

        # Calculate scores for each data point
        scored_data_points = data_points.map do |dp|
          # Different scoring for websites
          score = score_regular_data_point(dp, data_points)

          [dp, score]
        end

        # Return the data point with the highest score
        best_data_point = scored_data_points.max_by { |_dp, score| score }.first

        {
          "data" => best_data_point["data"],
          "source" => best_data_point["source"]
        }
      end

      def self.pick_best_term_dates(start_dates, end_dates)
        best_start_date = pick_best_data_point(start_dates)
        best_end_date = pick_best_data_point(end_dates)

        {
          "start_date" => best_start_date,
          "end_date" => best_end_date
        }
      end

      # Score a regular (non-website) data point
      def self.score_regular_data_point(data_point, all_data_points)
        # Count frequency
        value_counts = count_value_occurrences(all_data_points)

        # Basic scoring components
        confidence_score = data_point["llm_confidence"] || 0.5
        frequency = value_counts[data_point["data"]] || 0
        frequency_score = [frequency / 3.0, 1.0].min

        (frequency_score * 0.7) + (confidence_score * 0.3)
      end

      # Helper to count occurrences of each value
      def self.count_value_occurrences(data_points)
        value_counts = {}
        data_points.each do |dp|
          value = dp["data"]
          value_counts[value] ||= 0
          value_counts[value] += 1
        end
        value_counts
      end

      # Combines all data points into a single person hash
      def self.format_person(llm_person) # rubocop:disable Metrics/PerceivedComplexity
        term_date = pick_best_term_dates(llm_person["start_dates"], llm_person["end_dates"])
        selected_data_points = {
          "phone_number" => pick_best_data_point(llm_person["phone_numbers"]),
          "email" => pick_best_data_point(llm_person["emails"]),
          "website" => pick_best_data_point(llm_person["websites"]),
          "image" => pick_best_data_point(llm_person["images"]),
          **(term_date.present? ? term_date : {})
        }

        sources = selected_data_points.values.map { |dp| dp.present? ? dp["source"] : nil }.compact.uniq

        {
          "name" => llm_person["name"],
          "roles" => llm_person["roles"].map { |role| role["data"] }.uniq,
          "divisions" => llm_person["divisions"].map { |division| division["data"] }.uniq,
          "image" => selected_data_points["image"].present? ? selected_data_points["image"]["data"] : nil,
          "phone_number" => if selected_data_points["phone_number"].present?
                              selected_data_points["phone_number"]["data"]
                            end,
          "email" => selected_data_points["email"].present? ? selected_data_points["email"]["data"] : nil,
          "website" => selected_data_points["website"].present? ? selected_data_points["website"]["data"] : nil,
          "start_date" => (selected_data_points["start_date"]["data"] if selected_data_points["start_date"].present?),
          "end_date" => selected_data_points["end_date"].present? ? selected_data_points["end_date"]["data"] : nil,
          "sources" => (Array(llm_person["sources"]) + Array(sources)).uniq
        }
      end
    end
  end
end
