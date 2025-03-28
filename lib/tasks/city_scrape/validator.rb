module CityScrape
  class Validator
    def self.validate_fetch_inputs(state, gnis)
      if state.blank? || gnis.blank?
        puts "❌ Error: Missing required parameters"
        puts "Usage: rake 'city_info:fetch[wa,gnis]'"
        exit 1
      end

      if state_city_entry["website"].blank?
        puts "❌ Error: City website not found for #{city.capitalize}, #{state.upcase}"
        exit 1
      end
    end

    def self.validate_pick_cities(state, num_cities)
      # Move validation logic here
      end
    end
  end
end 
