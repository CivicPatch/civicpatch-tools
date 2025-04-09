require "text"

module Validators
  class Utils
    # Weights for different fields based on importance
    FIELD_WEIGHTS = {
      name: 0.5,
      position: 0.4,
      email: 0.3,
      phone_number: 0.3,
      website: 0.1
    }
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

        get_array_similarity(value1, value2)
      when "website"
        normalize_url(value1) == normalize_url(value2) ? 1.0 : 0.0
      else
        # Use Levenshtein for fuzzy matching on names, positions, and websites
        max_length = [value1.length, value2.length].max
        return 0.0 if max_length.zero?

        distance = Text::Levenshtein.distance(value1, value2)
        similarity = 1.0 - (distance.to_f / max_length)

        # Slight adjustment for position similarity
        similarity = 1.0 - (distance.to_f / (max_length + 2.0)) if [:position, "position"].include?(field)

        # Apply confidence weighting
        similarity * Math.sqrt(confidence_a * confidence_b)

      end
    end

    def self.get_array_similarity(array1, array2)
      total_similarity = 0.0

      array1.map do |item|
        if array2.include?(item)
          total_similarity += 1.0
        elsif array2.any? { |item2| Text::Levenshtein.distance(item, item2) <= 6 }
          total_similarity += 0.6
        else
          0.0
        end
      end

      total_similarity / (array1.size + array2.size).to_f
    end

    def self.overall_agreement_score(contested_people, total_people, total_fields)
      return 1.0 if total_people.zero? || total_fields.zero? # Avoid division by zero

      # Extract disagreement scores from all contested fields
      all_disagreement_scores = contested_people.values.flat_map do |fields|
        fields.values.map do |field|
          # Handle the case where field might be nil or not have a disagreement_score
          field.is_a?(Hash) && field[:disagreement_score].is_a?(Numeric) ? field[:disagreement_score] : 0.0
        end
      end

      # Calculate total agreement score
      total_disagreement = all_disagreement_scores.sum
      max_possible_disagreement = total_people * total_fields # Max disagreement is when all fields are fully contested

      1.0 - (total_disagreement.to_f / max_possible_disagreement)
    end

    def self.compare_people_across_sources(sources)
      contested_people = {}
      fields = %w[positions email phone_number website]

      # Normalize names across sources
      contested_names = normalize_names(sources)

      # Normalize person records based on contested names
      normalized_sources = apply_name_normalization(sources, contested_names)

      unique_names = get_unique_names(normalized_sources)
      total_people = unique_names.count
      total_fields = fields.count

      unique_names.each do |name|
        person_records = get_person_records(normalized_sources, name)

        existing_records = (person_records || []).select do |r|
          r[:people].present?
        end

        contested_fields = {}

        fields.each do |field|
          # Skip if there aren't at least two sources with a non-empty value for this field
          non_empty_count = existing_records.count do |r|
            r[:people]&.[](field).present? && r[:people][field] != ""
          end

          next if non_empty_count < 2

          # Compare the field values across sources
          contested_field_result = compare_field_values(existing_records, field)
          contested_fields[field] = contested_field_result if contested_field_result
        end

        contested_people[name] = contested_fields unless contested_fields.empty?
      end

      # Calculate the agreement score based on contested data
      agreement_score = overall_agreement_score(contested_people, total_people, total_fields)

      {
        contested_people: contested_people,
        agreement_score: agreement_score,
        contested_names: contested_names
      }
    end

    def self.compare_field_values(existing_records, field)
      pairwise_similarities = existing_records.combination(2).map do |a, b|
        value_a = a[:people][field]
        value_b = b[:people][field]

        conf_a = a[:confidence_score]
        conf_b = b[:confidence_score]

        if value_a.nil? || value_b.nil?
          1.0
        else
          similarity_score(field, value_a, value_b, conf_a, conf_b)
        end
      end

      worst_similarity = pairwise_similarities.min || 1.0
      return nil unless worst_similarity < DISAGREEMENT_THRESHOLD

      {
        disagreement_score: 1 - worst_similarity,
        values: existing_records.each_with_object({}) do |r, acc|
          acc[r[:source_name]] = r[:people][field]
        end
      }
    end

    def self.normalize_names(sources)
      canonical_names = sources[0][:people].map { |p| p["name"] }
      contested_names = Array.new(sources.size)

      sources.each_with_index do |source, i|
        next if i.zero?

        contested_names[i] = {}

        source[:people].each do |person|
          best_match = canonical_names.max_by do |canonical_name|
            similarity_score("name", person["name"], canonical_name, 1.0, 1.0)
          end

          similarity = similarity_score("name", person["name"], best_match, 1.0, 1.0)
          contested_names[i][person["name"]] = best_match if similarity >= 0.8 && person["name"] != best_match
        end
      end

      contested_names
    end

    def self.apply_name_normalization(sources, contested_names)
      sources.each_with_index.map do |source, i|
        name_map = contested_names[i] || {}
        source[:people] = source[:people].map do |person|
          canonical_name = name_map[person["name"]]
          person.merge("name" => canonical_name || person["name"])
        end
      end

      sources
    end

    def self.get_unique_names(normalized_sources)
      normalized_sources.flat_map { |s| s[:people].map { |p| p["name"] } }.uniq
    end

    def self.get_person_records(normalized_sources, name)
      normalized_sources.map do |source|
        {
          people: source[:people].find { |p| p["name"] == name },
          source_name: source[:source_name], # Keep extra fields so that each field has proximity to the source
          confidence_score: source[:confidence_score]
        }
      end
    end

    def self.merge_people_across_sources(sources, contested_names = [])
      merged = []

      # Apply contested name mappings to normalize names across sources
      normalized_sources = sources.each_with_index.map do |source, i|
        name_map = contested_names[i] || {}

        people = source[:people].map do |person|
          canonical_name = name_map[person["name"]]
          person.merge("name" => canonical_name || person["name"])
        end

        source.merge(people: people)
      end

      unique_names = normalized_sources.flat_map { |s| s[:people].map { |p| p["name"] } }.uniq

      unique_names.each do |name|
        person_records = normalized_sources.map do |source|
          person = source[:people].find { |p| p["name"] == name }
          next unless person

          person.merge("confidence_score" => source[:confidence_score], "source_name" => source[:source_name])
        end.compact

        next if person_records.empty?

        merged_person = { "name" => name }

        %w[positions email phone_number website image].each do |field|
          values = person_records.map { |p| { value: p[field], confidence_score: p["confidence_score"] } }

          merged_person[field] = select_best_value(field, values)
        end

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
  end
end
