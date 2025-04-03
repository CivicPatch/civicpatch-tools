require "text"

module Validators
  class Utils
    # Weights for different fields based on importance
    FIELD_WEIGHTS = {
      name: 0.5,
      position: 0.4,
      email: 0.3,
      phone: 0.3,
      website: 0.1
    }
    # Sources like MRSC or Secretary of State sites
    # might get outdated throughout the year.
    SOURCE_CONFIDENCES = [0.9, 0.7, 0.7]
    DISAGREEMENT_THRESHOLD = 0.9

    # Normalize text (downcase, strip whitespace)
    def self.normalize_text(text)
      text.to_s.strip.downcase
    end

    def self.normalize_phone(phone)
      phone.to_s.gsub(/\D/, "") # Keep only digits
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
      return 0.0 if value1.nil? || value2.nil? # Missing data = no match

      case field
      when :phone
        normalize_phone(value1) == normalize_phone(value2) ? 1.0 : 0.0
      when :email
        normalize_email(value1) == normalize_email(value2) ? 1.0 : 0.0
      when :positions
        return 0.0 unless value1.is_a?(Array) && value2.is_a?(Array)

        # If both positions are arrays, normalize and sort them before comparison

        sorted_value1 = value1.map { |v| normalize_text(v) }.sort
        sorted_value2 = value2.map { |v| normalize_text(v) }.sort

        # Compare the sorted arrays directly
        return 1.0 if sorted_value1 == sorted_value2

        similarities = sorted_value1.zip(sorted_value2).map do |pos_a, pos_b|
          similarity_score(:position, pos_a, pos_b)
        end
        similarities.sum / similarities.size.to_f
      else
        # Use Levenshtein for fuzzy matching on names, positions, and websites
        max_length = [value1.length, value2.length].max
        return 0.0 if max_length.zero?

        distance = Text::Levenshtein.distance(value1, value2)
        similarity = 1.0 - (distance.to_f / max_length)
        if field == :position
          similarity = 1.0 - (distance.to_f / (max_length + 2.0)) # Slightly increase the divisor to reduce penalty
        end
        similarity
      end
    end

    def self.overall_agreement_score(contested_people, total_people, total_fields)
      return 1.0 if total_people.zero? || total_fields.zero? # Avoid division by zero

      # Extract disagreement scores from all contested fields
      all_disagreement_scores = contested_people.values.flat_map do |fields|
        fields.values.map { |field| field[:disagreement_score] }
      end

      # Calculate total agreement score
      total_disagreement = all_disagreement_scores.sum
      max_possible_disagreement = total_people * total_fields # Max disagreement is when all fields are fully contested

      1.0 - (total_disagreement.to_f / max_possible_disagreement)
    end

    def self.compare_people_across_sources(sources, source_confidences)
      contested_people = {}

      # Gather all unique names across sources
      unique_names = sources.flatten(1).map { |p| p[:name] }.uniq
      total_people = unique_names.count
      fields = %i[positions email phone website]  # Updated 'position' to 'positions'
      total_fields = fields.count

      unique_names.each do |name|
        person_records = sources.map { |source| source.find { |p| p[:name] == name } }
        existing_records = person_records.compact # Remove nil entries (missing persons)

        contested_fields = {}

        fields.each_with_index do |field, index|
          # Only consider the field if there are at least two non-nil records
          next if existing_records.count { |r| r[field].present? } < 2

          pairwise_similarities = existing_records.combination(2).map do |record_a, record_b|
            value_a = record_a[field]
            value_b = record_b[field]

            # Find the index of the sources, handling the case when the record is not found
            source_index_a = sources.index { |source| source.include?(record_a) }
            source_index_b = sources.index { |source| source.include?(record_b) }

            # If either source is not found, we treat their confidence as 1 (neutral)
            confidence_a = source_index_a.nil? ? 1.0 : source_confidences[source_index_a]
            confidence_b = source_index_b.nil? ? 1.0 : source_confidences[source_index_b]

            # If the value is nil in any record, treat it as neutral (don't penalize)
            similarity = if value_a.nil? || value_b.nil?
                           1.0 # No penalty for missing values
                         else
                           similarity_score(field, value_a, value_b, confidence_a, confidence_b)
                         end
            similarity
          end.flatten

          worst_similarity = pairwise_similarities.min || 1.0

          next unless worst_similarity < DISAGREEMENT_THRESHOLD

          contested_fields[field] = {
            disagreement_score: 1 - worst_similarity,
            values: person_records.map { |r| r&.dig(field) }
          }
        end

        contested_people[name] = contested_fields unless contested_fields.empty?
      end

      # Compute overall agreement score
      agreement_score = overall_agreement_score(contested_people, total_people, total_fields)

      { contested_people: contested_people, agreement_score: agreement_score }
    end
  end
end
