require "text"

module Validators
  class Utils
    # Sources like MRSC or Secretary of State sites
    # might get outdated throughout the year.
    DISAGREEMENT_THRESHOLD = 0.9

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

    # Compute similarity score based on field type
    def self.similarity_score(field, value1, value2, confidence_a = 1.0, confidence_b = 1.0)
      return 1.0 if value1 == value2 # Exact match for any field
      return 0.9 if value1.nil? || value2.nil? # one is nil, treat as 90% similarity
      return 0.9 if value1.empty? || value2.empty? # one is empty, treat as 90% similarity
      return 1.0 if %w[sources].include?(field)

      case field
      when "phone_number"
        normalize_phone_number(value1) == normalize_phone_number(value2) ? 1.0 : 0.0
      when "email"
        normalize_email(value1) == normalize_email(value2) ? 1.0 : 0.0
      when "positions"
        return 0.0 unless value1.is_a?(Array) && value2.is_a?(Array)

        similarity = get_array_similarity(value1, value2)

        # Apply confidence weighting
        similarity * Math.sqrt(confidence_a * confidence_b)
      when "website"
        normalized_value1 = normalize_url(value1)
        normalized_value2 = normalize_url(value2)

        return 1.0 if normalized_value1 == normalized_value2

        get_text_similarity(normalized_value1, normalized_value2)
      else
        similarity = get_text_similarity(value1, value2)
        # Apply confidence weighting
        similarity * Math.sqrt(confidence_a * confidence_b)
      end
    end

    def self.get_text_similarity(value1, value2)
      return 1.0 if value1 == value2

      max_length = [value1.length, value2.length].max
      return 0.0 if max_length.zero?

      distance = Text::Levenshtein.distance(value1, value2)
      1.0 - (distance.to_f / max_length)
    end

    def self.get_array_similarity(array1, array2)
      return 1.0 if array1.sort == array2.sort

      total_similarity = 0.0
      total_items = array1.size + array2.size

      array1.each do |item1|
        # Check for exact match first
        if array2.include?(item1)
          total_similarity += 1.0
        else
          # Calculate Levenshtein similarity, but apply a higher weight for close matches
          best_match_score = array2.map do |item2|
            distance = Text::Levenshtein.distance(item1, item2)
            max_len = [item1.length, item2.length].max
            similarity = 1.0 - (distance.to_f / max_len)

            # Boost if the distance is low but the match is close (e.g., Council Member vs. Councilman)
            if distance <= 6
              similarity += 0.5 # Increase similarity for slight differences
            end

            similarity
          end.max || 0.0

          total_similarity += best_match_score
        end
      end

      # Normalize similarity based on the size of both arrays
      total_similarity / total_items.to_f
    end

    def self.compare_people_across_sources(people_config, sources)
      fields = %w[positions email phone_number website] # Fields to compare

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
            person: Core::PersonResolver.find_by_name(people_config, source[:people], name),
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
      non_nil_values = values.reject { |v| v[:value].nil? || v[:value] == "" || v[:value] == [] }
      return nil if non_nil_values.empty?

      # Group by normalized value (e.g., phone number, email, or text)
      grouped = non_nil_values.group_by do |v|
        case field
        when "positions"
          # NOTE: don't want to pick by confidence score here,
          # just by the common values between each source
          return merge_common_values(values.map { |val| val[:value] })
        when "email"
          normalize_email(v[:value])
        when "phone_number"
          normalize_phone_number(v[:value])
        when "website"
          normalize_url(v[:value])
        else
          normalize_text(v[:value])
        end
      end

      # Rank groups by their total confidence score
      best_group = grouped.max_by { |_val, group| group.sum { |v| v[:confidence_score] || 1.0 } }

      best_group.last.max_by { |v| v[:confidence_score] || 1.0 }[:value]
    end

    def self.merge_common_values(arrays)
      hash_counts = arrays.each_with_object(Hash.new(0)) do |array, aggregated_counts|
        array.uniq.each do |item|
          aggregated_counts[item] += 1
        end
      end

      hash_counts.keys.select { |key| hash_counts[key] > 1 }
    end

    # Helper to parse first and last name, ignoring middle parts and case
    def self.parse_name(full_name)
      return { first: nil, last: nil } if full_name.nil? || full_name.strip.empty?

      parts = full_name.strip.split(/\s+/)
      last_name = parts.pop || ""
      first_name = parts.shift || ""
      # Return downcased names
      { first: first_name.downcase, last: last_name.downcase }
    end
  end
end
