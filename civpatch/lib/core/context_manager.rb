# frozen_string_literal: true

module Core
  class ContextManager
    def self.get_context(state, geoid)
      config = Core::ConfigManager.get_config(state, geoid)
      municipality_entry = Core::StateManager.get_city_entry_by_geoid(state, geoid)
      {
        state: state,
        geoid: geoid,
        municipality_entry: municipality_entry,
        people: config["people"] || {},
        government_type: config["government_type"] || municipality_entry["government_type"],
        sources: config["sources"] || [],
        exclude_sources: config["exclude_sources"] || []
        # config: config
      }
    end
  end
end
