# frozen_string_literal: true

require "services/census"
require_relative "nh/municipalities"
require_relative "or/municipalities"
require_relative "wa/municipalities"

module Scrapers
  class Municipalities
    CENSUS_PLACES_POPULATION_API = "https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=place:*&in=state:"
    CENSUS_COUNTY_SUBDIVISIONS_POPULATION_API = "https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=county subdivision:*&in=state:"
    CENSUS_PLACES_MUNICIPALITIES_CODES = "https://www2.census.gov/geo/docs/reference/codes2020/place"
    CENSUS_COUNTY_SUBDIVISIONS_MUNICIPALITIES_CODES = "https://www2.census.gov/geo/docs/reference/codes2020/cousub"

    CENSUS_URL_MAPPINGS = {
      "places_txt_url" => lambda { |state, statefp|
        "#{CENSUS_PLACES_MUNICIPALITIES_CODES}/st#{statefp}_#{state}_place2020.txt"
      },
      "cousub_txt_url" => lambda { |state, statefp|
        "#{CENSUS_COUNTY_SUBDIVISIONS_MUNICIPALITIES_CODES}/st#{statefp}_#{state}_cousub2020.txt"
      },
      "places_api_url" => lambda { |statefp|
        "#{CENSUS_PLACES_POPULATION_API}#{statefp}"
      },
      "cousub_api_url" => lambda { |statefp|
        "#{CENSUS_COUNTY_SUBDIVISIONS_POPULATION_API}#{statefp}"
      }
    }.freeze

    def self.get_scraper(state)
      case state
      when "nh"
        Scrapers::Nh::Municipalities
      when "or"
        Scrapers::Or::Municipalities
      when "wa"
        Scrapers::Wa::Municipalities
      else
        raise "No scraper found for #{state}"
      end
    end

    def self.fetch(state)
      scraper = get_scraper(state)
      statefp = Services::Census::STATE_TO_STATEFP[state]

      raise "No statefp found for #{state}" if statefp.nil?

      municipalities_with_census_data = fetch_census_data(state, statefp)
      descending = -1
      municipalities_with_census_data = municipalities_with_census_data
                                        .sort_by { |m| m["population"] * descending }
      additional_info_hash_by_municipality_name = scraper.fetch

      municipalities_with_census_data.map do |m|
        if additional_info_hash_by_municipality_name.nil?
          puts "No additional info found for #{m["name"]}"
          next m
        end

        # NOTE: Need to specify by county for states with duplicates.
        # See: Michigan
        {
          **m,
          **additional_info_hash_by_municipality_name[m["name"]]
          # Properties available:
          # address
          # phone_number
          # website
          # email
          # government_type
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
      places_txt_url = CENSUS_URL_MAPPINGS["places_txt_url"].call(state, statefp)
      puts "Fetching census municipality codes from places: #{places_txt_url}"
      response = HTTParty.get(places_txt_url)
      places_csv = CSV.parse(response.body, headers: true, col_sep: "|")

      places = places_csv.map(&:to_h)
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

      county_subdivisions_txt_url = CENSUS_URL_MAPPINGS["cousub_txt_url"].call(state, statefp)
      puts "Fetching census municipality codes from county subdivisions: #{county_subdivisions_txt_url}"
      response = HTTParty.get(county_subdivisions_txt_url)
      county_subdivisions_csv = CSV.parse(response.body, headers: true, col_sep: "|")

      county_subdivisions = county_subdivisions_csv.map do |municipality_codes|
        name, type = get_municipality_name_and_type(municipality_codes["COUSUBNAME"])
        {
          "name" => name,
          "type" => type,
          "fips" => "#{statefp}-#{municipality_codes["COUSUBFP"]}",
          "gnis" => format_gnis(municipality_codes["COUSUBNS"]),
          "counties" => format_counties(municipality_codes["COUNTYNAME"])
        }
      end

      places + county_subdivisions
    end

    def self.get_municipality_name_and_type(placename)
      parts = placename.split(" ")
      name = parts.take(parts.length - 1).join(" ")
      type = parts.last

      [name, type]
    end

    def self.fetch_census_populations(statefp)
      hash_fips_to_population = {}
      county_subdivisions_api_url = "#{CENSUS_COUNTY_SUBDIVISIONS_POPULATION_API}#{statefp}"
      places_api_url = "#{CENSUS_PLACES_POPULATION_API}#{statefp}"

      county_subdivisions_response = HTTParty.get(county_subdivisions_api_url)
      places_response = HTTParty.get(places_api_url)

      county_subdivisions_json = JSON.parse(county_subdivisions_response.body)
      places_json = JSON.parse(places_response.body)

      county_subdivisions_json.drop(1).each do |row|
        placefp = row[4]
        population = row[0]
        hash_fips_to_population[placefp] = population.to_i
      end

      places_json.drop(1).each do |row|
        placefp = row[3]
        population = row[0]
        hash_fips_to_population[placefp] = population.to_i
      end

      hash_fips_to_population
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
