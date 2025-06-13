# frozen_string_literal: true

require "services/google_search"
require "services/brave"
require "utils/array_helper"

module Resolvers
  class SearchResolver
    SEARCH_SERVICES = {
      "google" => Services::GoogleSearch,
      "brave" => Services::Brave
    }.freeze

    def self.municipal_search(municipality_context, keyword_term_groups)
      urls_by_keywords = keyword_term_groups.map do |keyword_term_group|
        do_municipal_search(municipality_context, keyword_term_group)
      end

      # interleave the urls by keywords
      Utils::ArrayHelper.interleave_arrays(urls_by_keywords)&.uniq
    end

    def self.do_municipal_search(municipality_context, keyword_term_group)
      query_keywords = keyword_term_group[:name]
      or_terms_list = keyword_term_group[:keywords]

      SEARCH_SERVICES.each do |search_engine_name, search_service|
        keyword_with_type = "#{municipality_context[:municipality_entry]["type"]} #{query_keywords}"
        or_terms = or_terms_list.join("|")
        puts "Searching with #{search_engine_name} for #{keyword_with_type}"
        results = search_service.municipal_search(municipality_context, keyword_with_type, or_terms_list)
        Utils::CostsHelper.log_search_engine_call(municipality_context[:state],
                                                  municipality_context[:municipality_entry]["name"], search_engine_name)
        puts "Search successful with #{search_engine_name}."
        return results # Return results immediately on success
      rescue StandardError => e
        puts "Error with #{search_engine_name}: #{e.message}. Trying next service..."
        next
      end

      puts "Error: All search services failed for municipality: #{municipality_context}"
      []
    end
  end
end
