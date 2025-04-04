require_relative "../../scrapers/states/wa/city_directory"

module Sources
  module StateSource
    class CityDirectory
      def self.get_city_directory(state, gnis)
        state_source = get_state_source(state)
        directory = state_source.get_city_directory(gnis)
        directory.map do |person|
          Scrapers::Standard.normalize_source_person(person)
        end
      end

      def self.get_state_source(state)
        case state
        when "wa"
          Scrapers::States::Wa::CityDirectory
        else
          raise "No state source found for state: #{state}"
        end
      end
    end
  end
end
