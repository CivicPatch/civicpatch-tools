require "scrapers/common"

module Services
  module Shared
    class People
      def self.format_raw_data(person, source)
        formatted_person = {
          "name" => person["name"],
          "image" => person["image"]
        }
        formatted_person["phone_numbers"] =
          data_point?(person["phone_number"]) ? [person["phone_number"]] : []
        formatted_person["emails"] =
          data_point?(person["email"]) ? [person["email"]] : []
        formatted_person["websites"] =
          data_point?(person["website"]) ? [format_website_data_point(person["website"])] : []
        formatted_person["term_dates"] =
          data_point?(person["term_date"]) ? [person["term_date"]] : []
        formatted_person["positions"] = person["positions"].present? ? person["positions"] : []

        data_points_with_source(formatted_person, source)
      end

      def self.merge_person(person, partial_person)
        merged = person.dup
        merged["image"] = partial_person["image"] || person["image"]
        merged["phone_numbers"] += partial_person["phone_numbers"]
        merged["emails"] += partial_person["emails"]
        merged["websites"] += partial_person["websites"]
        merged["term_dates"] += partial_person["term_dates"]
        merged["positions"] = (Array(person["positions"]) + Array(partial_person["positions"])).uniq
        merged["sources"] = (Array(person["sources"]) + Array(partial_person["sources"])).uniq

        merged
      end

      def self.collect_people(people, partial_people)
        people_by_name = {}
        people.each do |person|
          people_by_name[person["name"]] = person
        end

        partial_people.each do |partial_person|
          name = partial_person["name"]
          existing_person = Validators::Utils.find_by_name(people, name)

          if existing_person.present?
            existing_name = existing_person["name"]
            people_by_name[name] = merge_person(existing_person, partial_person)
          else
            people_by_name[name] = partial_person
          end
        end

        people_by_name.values
      end

      def self.format_website_data_point(website_data_point)
        website_data_point["data"] = Utils::UrlHelper.format_url(website_data_point["data"])
        website_data_point
      end

      def self.data_points_with_source(person, source)
        %w[phone_numbers emails websites term_dates].each do |data_point|
          next unless person[data_point].present?

          person[data_point].each do |data_point_item|
            data_point_item["source"] = Utils::UrlHelper.format_url(source)
          end
        end

        person
      end

      def self.data_point?(data_point)
        data_point.present? && data_point["data"].present? && data_point["data"].to_s.strip.present?
      end

      def self.profile_data_points_present?(person)
        person["positions"].present? && person["positions"].count.positive? &&
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
          if dp["data"].is_a?(String) && dp["data"].include?("http")
            score = score_regular_data_point(dp, data_points) + score_website(dp, data_points)
          else
            score = score_regular_data_point(dp, data_points)
          end

          [dp, score]
        end

        # Return the data point with the highest score
        best_data_point = scored_data_points.max_by { |_dp, score| score }.first

        {
          "data" => best_data_point["data"],
          "source" => best_data_point["source"],
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

        # Formatting score
        formatting_score = if data_point["markdown_formatting"] && data_point["markdown_formatting"]["in_list"]
                             0.8
                           else
                             0.2
                           end

        # Standard scoring
        (frequency_score * 0.5) + (confidence_score * 0.3) + (formatting_score * 0.2)
      end

      # Score a website data point with special website-specific factors
      def self.score_website(website, all_websites)
        url = website["data"]
        source_urls = all_websites.map { |w| w["source"] }.compact

        # Penalize websites that match source URLs because we've already
        # scraped them
        source_urls.include?(url) ? -0.5 : 0
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
      def self.format_person(llm_person)
        selected_data_points = {
          "phone_number" => pick_best_data_point(llm_person["phone_numbers"]),
          "email" => pick_best_data_point(llm_person["emails"]),
          "website" => pick_best_data_point(llm_person["websites"]),
          "term_date" => pick_best_data_point(llm_person["term_dates"])
        }

        sources = selected_data_points.values.map { |dp| dp.present? ? dp["source"] : nil }.compact.uniq

        person = {
          "name" => llm_person["name"],
          "positions" => llm_person["positions"],
          "image" => llm_person["image"],
          "phone_number" => selected_data_points["phone_number"].present? ? selected_data_points["phone_number"]["data"] : nil,
          "email" => selected_data_points["email"].present? ? selected_data_points["email"]["data"] : nil,
          "website" => selected_data_points["website"].present? ? selected_data_points["website"]["data"] : nil,
          "term_date" => selected_data_points["term_date"].present? ? selected_data_points["term_date"]["data"] : nil,
          "sources" => sources
        }

        person
      end
    end
  end
end
