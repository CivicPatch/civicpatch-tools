# frozen_string_literal: true

require "text"

module Validators
  class Utils
    # Normalize text (downcase, strip whitespace)
    def self.normalize_text(text)
      text.to_s.strip.downcase
    end

    def self.normalize_phone_number(phone_number)
      phone_number.to_s.gsub(/\D/, "") # Keep only digits
    end

    # Normalize emails (ignore case)
    def self.normalize_email(email)
      return nil if email.nil?

      email = normalize_text(email)
      local, domain = email.split("@", 2)
      return email unless domain # If malformed, return as is

      normalized_local = local.gsub(".", "") # Remove all dots from the username
      "#{normalized_local}@#{domain}"
    end

    def self.normalize_url(url)
      return nil if url.nil?

      url = normalize_text(url)
      url.gsub("www.", "")
    end

    def self.merge_people_across_sources(people_config, sources)
      return sources.first[:people] if sources.count == 1

      merged = []

      unique_names = sources.map { |s| s[:people].map { |p| p["name"] } }.flatten.uniq

      unique_names.each do |name|
        person_records = sources.map do |source|
          person = Core::PersonResolver.find_by_name(people_config, source[:people], name)
          next unless person

          person.merge("confidence_score" => source[:confidence_score], "source_name" => source[:source_name])
        end.compact

        next if person_records.empty?

        merged_person = { "name" => name }

        %w[positions email phone_number website start_date end_date].each do |field|
          values = person_records.map { |p| { value: p[field], confidence_score: p["confidence_score"] } }

          merged_person[field] = select_best_value(field, values)
        end

        merged_person["image"] = person_records.map { |p| p["image"] }.compact.first
        merged_person["source_image"] = person_records.map { |p| p["source_image"] }.compact.first
        merged_person["sources"] = person_records.map { |p| p["sources"] }.flatten.compact.uniq

        merged << merged_person
      end

      merged
    end

    def self.select_best_value(field, values)
      non_nil_values = filter_valid_values(values)
      return nil if non_nil_values.empty?
      return merge_common_values(values.map { |v| v[:value] }) if field == "positions"

      find_best_value(non_nil_values, field)
    end

    private_class_method def self.filter_valid_values(values)
      values.reject { |v| v[:value].nil? || v[:value].empty? }
    end

    private_class_method def self.find_best_value(values, field)
      grouped = values.group_by { |v| normalize_value(field, v[:value]) }
      best_group = find_best_group(grouped)
      best_group.last.max_by { |v| v[:confidence_score] || 1.0 }[:value]
    end

    private_class_method def self.find_best_group(grouped)
      grouped.max_by { |_, group| group.sum { |v| v[:confidence_score] || 1.0 } }
    end

    private_class_method def self.normalize_value(field, value)
      case field
      when "email" then normalize_email(value)
      when "phone_number" then normalize_phone_number(value)
      when "website" then normalize_url(value)
      else normalize_text(value)
      end
    end

    private_class_method def self.merge_common_values(arrays)
      hash_counts = arrays.each_with_object(Hash.new(0)) do |array, aggregated_counts|
        array.uniq.each do |item|
          aggregated_counts[item] += 1
        end
      end

      hash_counts.keys.select { |key| hash_counts[key] > 1 }
    end
  end
end
