# frozen_string_literal: true

require "services/google_search"
require "services/brave"
require "utils/array_helper"

module Resolvers
  class SearchResolver
    SEARCH_SERVICES = [
      Services::GoogleSearch,
      Services::Brave
    ].freeze

    def self.municipal_search(municipality_context, keyword_terms)
      urls_by_keywords = keyword_terms.map do |keyword_term|
        do_municipal_search(municipality_context, keyword_term)
      end

      # interleave the urls by keywords
      Utils::ArrayHelper.interleave_arrays(urls_by_keywords)&.uniq
    end

    def self.do_municipal_search(municipality_context, query_keywords)
      SEARCH_SERVICES.each do |search_service|
        puts "Searching with #{search_service.name} for #{query_keywords}"
        results = search_service.municipal_search(municipality_context, query_keywords)
        puts "Search successful with #{search_service.name}."
        return results # Return results immediately on success
      rescue StandardError => e
        puts "Error with #{search_service.name}: #{e.message}. Trying next service..."
        next
      end

      puts "Error: All search services failed for municipality: #{municipality_context}"
      []
    end
  end
end
