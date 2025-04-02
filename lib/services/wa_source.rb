module Services
  class WaSource
    STATE_SOURCE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles"
    STATE_SOURCE_CITY_PAGE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles/city-officials"

    def self.get_places_list
      response = HTTParty.get(STATE_SOURCE_URL)
      document = Nokogiri::HTML(response.body)

      data = document.css("#tableCityProfiles").attr("data-data")
      cities = JSON.parse(data)
      cities.map do |city|
        {
          "name" => city["CityName"],
          "city_id" => city["CityID"],
          "website" => city["Website"],
          "government_type" => city["FormofGov"]
        }
      end
    end
  end
end
