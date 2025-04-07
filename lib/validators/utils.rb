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

    # Compute similarity score based on field type
    def self.similarity_score(field, value1, value2, confidence_a = 1.0, confidence_b = 1.0)
      return 1.0 if value1 == value2 # Exact match for any field
      return 0.5 if value1.nil? || value2.nil? # one is nil, treat as 50% similarity
      return 0.5 if value1.empty? || value2.empty? # one is empty, treat as 50% similarity
      return 1.0 if %w[sources].include?(field)

      case field
      when "phone_number"
        normalize_phone_number(value1) == normalize_phone_number(value2) ? 1.0 : 0.0
      when "email"
        normalize_email(value1) == normalize_email(value2) ? 1.0 : 0.0
      when "positions"
        return 0.0 unless value1.is_a?(Array) && value2.is_a?(Array)

        normalized1 = value1.map { |v| normalize_text(v) }
        normalized2 = value2.map { |v| normalize_text(v) }

        # Compare each role in value1 to the best match in value2
        total_similarity = 0.0
        normalized1.each do |pos1|
          best_match_score = normalized2.map { |pos2| similarity_score("position", pos1, pos2) }.max || 0.0
          total_similarity += best_match_score
        end

        average_similarity = total_similarity / normalized1.size.to_f
        average_similarity * Math.sqrt(confidence_a * confidence_b)
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

    def self.compare_people_across_sources(sources, source_confidences)
      contested_people = {}
      contested_names = Array.new(sources.size) # One hash per source
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
        existing_records = person_records.compact

        contested_fields = {}

        fields.each do |field|
          next if existing_records.count { |r| r[field].present? } < 2

          contested_field_result = compare_field_values(existing_records, field, sources, source_confidences)
          contested_fields[field] = contested_field_result if contested_field_result
        end

        contested_people[name] = contested_fields unless contested_fields.empty?
      end

      agreement_score = overall_agreement_score(contested_people, total_people, total_fields)

      {
        contested_people: contested_people,
        agreement_score: agreement_score,
        contested_names: contested_names
      }
    end

    def self.compare_field_values(existing_records, field, sources, source_confidences)
      pairwise_similarities = existing_records.combination(2).map do |a, b|
        value_a = a[field]
        value_b = b[field]

        # If both values are nil, skip the comparison for this field
        next if value_a.nil? && value_b.nil?

        index_a = sources.index { |s| s.include?(a) }
        index_b = sources.index { |s| s.include?(b) }

        conf_a = index_a.nil? ? 1.0 : source_confidences[index_a]
        conf_b = index_b.nil? ? 1.0 : source_confidences[index_b]

        similarity_score(field, value_a, value_b, conf_a, conf_b)
      end.compact # Remove nil similarities

      worst_similarity = pairwise_similarities.min || 1.0
      return nil if worst_similarity == 1.0 # If no disagreement, we can return nil for this field

      { disagreement_score: 1 - worst_similarity, values: existing_records.map { |r| r&.dig(field) }.compact }
    end

    def self.normalize_names(sources)
      canonical_names = sources[0].map { |p| p["name"] }
      contested_names = Array.new(sources.size)

      sources.each_with_index do |source, i|
        next if i == 0

        contested_names[i] = {}

        source.each do |person|
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
        source.map do |person|
          canonical_name = name_map[person["name"]]
          person.merge("name" => canonical_name || person["name"])
        end
      end
    end

    def self.get_unique_names(normalized_sources)
      normalized_sources.flatten(1).map { |p| p["name"] }.uniq
    end

    def self.get_person_records(normalized_sources, name)
      normalized_sources.map { |source| source.find { |p| p["name"] == name } }
    end

    def self.compare_field_values(existing_records, field, sources, source_confidences)
      pairwise_similarities = existing_records.combination(2).map do |a, b|
        value_a = a[field]
        value_b = b[field]

        index_a = sources.index { |s| s.include?(a) }
        index_b = sources.index { |s| s.include?(b) }

        conf_a = index_a.nil? ? 1.0 : source_confidences[index_a]
        conf_b = index_b.nil? ? 1.0 : source_confidences[index_b]

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
        values: existing_records.map { |r| r&.dig(field) }
      }
    end

    def self.merge_people_across_sources(sources, source_confidences, contested_people, contested_names = [])
      merged = []

      # Apply contested name mappings to normalize names across sources
      normalized_sources = sources.each_with_index.map do |source, i|
        name_map = contested_names[i] || {}

        source.map do |person|
          canonical_name = name_map[person["name"]]
          person.merge("name" => canonical_name || person["name"])
        end
      end

      # Collect unique canonical names
      unique_names = normalized_sources.flatten(1).map { |p| p["name"] }.uniq

      unique_names.each do |name|
        # Gather person records across sources for this name
        person_records = normalized_sources.map { |source| source.find { |p| p["name"] == name } }.compact
        next if person_records.empty?

        merged_person = { "name" => name }

        %w[positions email phone_number website image].each do |field|
          contested = contested_people[name]&.[](field)

          merged_person[field] = if contested.nil? || contested[:disagreement_score] < DISAGREEMENT_THRESHOLD
                                   merge_field(field, person_records.map { |p| p[field] })
                                 elsif field == "positions"
                                   merge_field("positions", person_records.map { |p| p["positions"] })
                                 else
                                   merge_field(field, person_records.map { |p| p[field] })
                                 end
        end

        merged_person["sources"] = merge_field("sources", person_records.map { |p| p["sources"] })

        merged << merged_person
      end

      merged
    end

    # Helper function to merge fields (returns the first non-nil value)
    def self.merge_field(field, values)
      non_nil = values.compact.uniq

      case field
      when "positions"
        non_nil.flatten.uniq
      when "email", "website", "image"
        non_nil.first
      when "phone_number"
        non_nil.max_by { |v| v.is_a?(Hash) ? v.values.join.length : v.to_s.length }
      when "sources"
        non_nil.flatten.uniq # Merge sources similarly to how we handle positions
      else
        non_nil.first
      end
    end
  end
end
