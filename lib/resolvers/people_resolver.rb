# frozen_string_literal: true

require "validators/utils"

module Resolvers
  class PeopleResolver
    DISAGREEMENT_THRESHOLD = 0.9

    def self.resolve(municipality_context)
      state = municipality_context[:state]
      gnis = municipality_context[:municipality_entry]["gnis"]
      state_source = municipality_context[:config]["source_directory_list"]["people"]
      people_config = municipality_context[:config]["people"]

      sources_folder_path = PathHelper.get_people_sources_path(state, gnis)
      source_files = Dir.glob(File.join(sources_folder_path, "*.json"))

      sources = [{
        source_name: "state_source",
        people: state_source,
        confidence_score: 0.9
      }]
      source_files.each do |source_file|
        next if source_file.include?("before") # Discard unprocessed results

        source_people = JSON.parse(File.read(source_file))
        source_name = if source_file.include?("openai")
                        "openai"
                      elsif source_file.include?("gemini")
                        "gemini"
                      end

        source = {
          source_name: source_name,
          people: source_people,
          confidence_score: case source_name
                            when "openai"
                              0.7
                            when "gemini"
                              0.7
                            else
                              0.0
                            end
        }
        sources << source
      end

      {
        compare_results: compare_people_across_sources(people_config, sources),
        merged_sources: merge_people_across_sources(people_config, sources)
      }
    end

    def self.compare_people_across_sources(people_config, sources) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity
      File.write("scratch.json", JSON.pretty_generate(sources))

      fields = %w[positions email phone_number website start_date end_date] # Fields to compare

      unique_names = sources.map { |s| s[:people].map { |p| p["name"] } }.flatten.uniq
      total_people = unique_names.count
      total_fields = fields.count
      num_sources = sources.count

      if total_people.zero? || num_sources.zero? || total_fields.zero?
        return { contested_people: {},
                 agreement_score: 100.0 }
      end

      total_possible_data_points = total_people * num_sources * total_fields
      total_disagreements = 0
      detailed_contested_fields = {}
      missing_people_report = {}

      unique_names.each do |name|
        person_records = sources.map do |source|
          {
            person: Resolvers::PersonResolver.find_by_name(people_config, source[:people], name),
            source_name: source[:source_name],
            confidence_score: source[:confidence_score]
          }
        end

        existing_records = person_records.select { |r| r[:person].present? }

        found_in_sources_count = existing_records.count
        missing_sources_count = num_sources - found_in_sources_count

        person_contested_fields = {}

        if missing_sources_count.positive?
          missing_from_sources = person_records.select { |r| r[:person].nil? }
                                               .map { |r| r[:source_name] }
          # Add to the separate missing people report
          missing_people_report[name] = missing_from_sources

          # Increment total disagreements (as done before)
          total_disagreements += missing_sources_count * total_fields
        end

        if found_in_sources_count >= 2
          fields.each do |field|
            contested_field_result = compare_field_values(existing_records, field)
            if contested_field_result
              total_disagreements += 1 # Increment overall disagreement count
              person_contested_fields[field] = contested_field_result
            end
          end
        end

        detailed_contested_fields[name] = person_contested_fields unless person_contested_fields.empty?
      end

      # Calculate agreement score (0-100, higher is better)
      agreement_score = ((total_possible_data_points - total_disagreements).to_f / total_possible_data_points) * 100
      agreement_score = [0, agreement_score].max # Ensure score is not negative
      agreement_score = [100, agreement_score].min # Ensure score does not exceed 100

      {
        contested_people: detailed_contested_fields,
        missing_people: missing_people_report,
        agreement_score: agreement_score.round(2)
      }
    end

    def self.merge_people_across_sources(people_config, sources) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/PerceivedComplexity
      return sources.first[:people] if sources.count == 1

      merged = []

      unique_names = sources.map { |s| s[:people].map { |p| p["name"] } }.flatten.uniq

      unique_names.each do |name|
        person_records = sources.map do |source|
          person = Resolvers::PersonResolver.find_by_name(people_config, source[:people], name)
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

    def self.compare_field_values(existing_records, field)
      pairwise_similarities = existing_records.combination(2).map do |a, b|
        # Check if a or b is nil before accessing keys
        unless a && b
          puts "ERROR: Found nil in pair: a=#{a.inspect}, b=#{b.inspect}"
          next 1.0 # Treat as max similarity if pair is malformed
        end

        value_a = a[:person][field]
        value_b = b[:person][field]

        conf_a = a[:confidence_score]
        conf_b = b[:confidence_score]

        if value_a.nil? || value_b.nil?
          0.9 # Treat nil value comparison as 90% similarity
        else
          similarity_score(field, value_a, value_b, conf_a, conf_b)
        end
      end

      worst_similarity = pairwise_similarities.min || 1.0
      return nil unless worst_similarity < DISAGREEMENT_THRESHOLD

      {
        disagreement_score: 1 - worst_similarity,
        values: existing_records.each_with_object({}) do |r, acc|
          # Ensure r is not nil before accessing :source_name and :person
          if r
            acc[r[:source_name]] = r[:person][field]
          else
            puts "WARN: Encountered nil record when building final values hash for field '#{field}'"
          end
        end
      }
    end

    # Compute similarity score based on field type
    def self.similarity_score(field, value1, value2, confidence_a = 1.0, confidence_b = 1.0)
      return 1.0 if value1 == value2
      return 0.8 if value1.empty? || value2.empty? # one is empty, treat as 90% similarity

      case field
      when "phone_number"
        Validators::Utils.normalize_phone_number(value1) == Validators::Utils.normalize_phone_number(value2) ? 1.0 : 0.0
      when "email"
        Validators::Utils.normalize_email(value1) == Validators::Utils.normalize_email(value2) ? 1.0 : 0.0
      when "positions"
        return 0.0 unless value1.is_a?(Array) && value2.is_a?(Array)

        similarity = get_array_similarity(value1, value2)

        # Apply confidence weighting
        similarity * Math.sqrt(confidence_a * confidence_b)
      when "website"
        normalized_value1 = Validators::Utils.normalize_url(value1)
        normalized_value2 = Validators::Utils.normalize_url(value2)

        normalized_value1 == normalized_value2 ? 1.0 : 0.0
      when "start_term_date", "end_term_date"
        # Term dates are either the same or they or not
        0.0
      else # Should never reach this point
        similarity = get_text_similarity(value1, value2)
        # Apply confidence weighting
        similarity * Math.sqrt(confidence_a * confidence_b)
      end
    end

    def self.get_array_similarity(array1, array2)
      intersection_size = (array1 & array2).size

      union_size = (array1 | array2).size

      if union_size.zero?
        1.0
      else
        intersection_size.to_f / union_size
      end
    end

    def self.get_text_similarity(value1, value2)
      return 1.0 if value1 == value2

      max_length = [value1.length, value2.length].max
      return 0.0 if max_length.zero?

      distance = Text::Levenshtein.distance(value1, value2)
      1.0 - (distance.to_f / max_length)
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
      when "email" then Validators::Utils.normalize_email(value)
      when "phone_number" then Validators::Utils.normalize_phone_number(value)
      when "website" then Validators::Utils.normalize_url(value)
      else Validators::Utils.normalize_text(value)
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
