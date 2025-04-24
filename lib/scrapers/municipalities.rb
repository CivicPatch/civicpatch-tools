require_relative "wa/municipalities"
require_relative "or/municipalities"

module Scrapers
  class Municipalities
    CENSUS_POPULATION_API = "https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=place:*&in=state:"
    CENSUS_MUNICIPALITIES_CODES = "https://www2.census.gov/geo/docs/reference/codes2020/place"

    STATE_TO_STATEFP = {
      "wa" => "53",
      "or" => "41"
    }.freeze

    def self.get_scraper(state)
      case state
      when "wa"
        Scrapers::Wa::Municipalities
      when "or"
        Scrapers::Or::Municipalities
      else
        raise NotImplementedError
      end
    end

    def self.fetch(state)
      scraper = get_scraper(state)
      statefp = STATE_TO_STATEFP[state]

      raise "No statefp found for #{state}" if statefp.nil?

      municipalities_with_census_data = fetch_census_data(state, statefp)
      descending = -1
      municipalities_with_census_data = municipalities_with_census_data
                                        .sort_by { |m| m["population"] * descending }
      additional_info_hash_by_municipality_name = scraper.fetch

      municipalities_with_census_data.map do |m|
        # NOTE: Need to specify by county for states with duplicates.
        # See: Michigan
        {
          **m,
          **additional_info_hash_by_municipality_name[m["name"]]
        }
      end
    end

    def self.fetch_census_data(state, statefp)
      census_municipality_codes = fetch_census_municipality_codes(state, statefp)
      populations_hash = fetch_census_populations(statefp)

      census_municipality_codes.map do |census_municipality_code_data|
        placefp = census_municipality_code_data["fips"].split("-").last
        population = populations_hash[placefp]

        {
          **census_municipality_code_data,
          "population" => population
        }
      end
    end

    def self.fetch_census_municipality_codes(state, statefp)
      url = "#{CENSUS_MUNICIPALITIES_CODES}/st#{statefp}_#{state}_place2020.txt"

      puts "Fetching census municipality codes: #{url}"
      response = HTTParty.get(url)
      csv = CSV.parse(response.body, headers: true, col_sep: "|")

      csv.map(&:to_h)
         .reject { |row| row["TYPE"] == "CENSUS DESIGNATED PLACE" }
         .map do |municipality_codes|
           name, type = get_municipality_name_and_type(municipality_codes["PLACENAME"])
           {
             "name" => name,
             "type" => type,
             "fips" => "#{statefp}-#{municipality_codes["PLACEFP"]}",
             "gnis" => format_gnis(municipality_codes["PLACENS"]),
             "counties" => format_counties(municipality_codes["COUNTIES"])
           }
         end
    end

    def self.get_municipality_name_and_type(placename)
      parts = placename.split(" ")
      name = parts.take(parts.length - 1).join(" ")
      type = parts.last

      [name, type]
    end

    def self.fetch_census_populations(statefp)
      url = "#{CENSUS_POPULATION_API}#{statefp}"

      response = HTTParty.get(url)
      JSON.parse(response.body)

      response.each_with_object({}) do |row, hash|
        placefp = row[3]
        population = row[0]
        hash[placefp] = population.to_i
      end
    end

    def self.format_municipality(statefp, placefp)
      {
        statefp: statefp,
        placefp: placefp
      }
    end

    def self.format_gnis(fips)
      fips&.sub(/^0/, "")
    end

    def self.format_counties(counties)
      counties.split("~~~").map { |county| format_county_name(county) }
    end

    def self.format_county_name(county)
      county&.sub(/\s+County$/, "")
    end
  end
end
