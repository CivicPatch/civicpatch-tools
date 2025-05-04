module Core
  class ContextManager
    def self.get_context(state, gnis)
      config = Core::ConfigManager.get_config(state, gnis)
      municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, gnis)
      government_type = Scrapers::Municipalities.get_government_type(state, municipality_entry)

      {
        state: state,
        municipality_entry: municipality_entry,
        government_type: government_type,
        config: config
      }
    end

    def self.update_context_config(municipality_context, **updates)
      updated_context = municipality_context.dup
      updated_context[:config] = updated_context[:config].merge(updates.stringify_keys)
      updated_context
    end
  end
end
