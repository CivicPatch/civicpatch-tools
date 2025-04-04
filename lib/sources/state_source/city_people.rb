require_relative "../../scrapers/states/wa/city_people"

module Sources
  module StateSource
    class CityPeople
      def self.get_city_people(state, gnis)
        state_source = get_state_source(state)
        people = state_source.get_city_people(gnis)
        people.map do |person|
          Scrapers::Standard.normalize_source_person(person)
        end
      end

      def self.get_state_source(state)
        case state
        when "wa"
          Scrapers::States::Wa::CityPeople
        else
          raise "No state source found for state: #{state}"
        end
      end
    end
  end
end
