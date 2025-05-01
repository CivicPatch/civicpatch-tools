module Scrapers::Wa::MunicipalityOfficials
  class StateLevelScraper
    DIRECTORY_URL = "https://mrsc.org/mrsctools/officials-directory/city.aspx".freeze
    CITY_AND_TOWN_PROFILES_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles".freeze
    EDIT_OFFICIALS_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles/city-officials".freeze

    @@html_cache ||= {}

    def self.get_source_url(city_entry)
      city_initial = city_entry["name"][0]
      "#{DIRECTORY_URL}?ci=#{city_initial}"
    end

    def self.get_suggest_edit_details(municipality_entry)
      # response = HTTParty.get(CITY_AND_TOWN_PROFILES_URL)
      # html_doc = Nokogiri::HTML(response.body)
      # current_date = Time.now.strftime("%Y-%m-%d")
      # File.write(File.join(__dir__, "cache", "#{current_date}_city_and_town_profiles.html"), response.body)
      cache_path = File.join(__dir__, "cache", "2025-05-01_city_and_town_profiles.html")
      response = File.read(cache_path)
      html_doc = Nokogiri::HTML(response)

      target_name = municipality_entry["name"]

      table = html_doc.at_css("#tableCityProfiles")
      data_data = table["data-data"]
      data = JSON.parse(data_data)
      matched_row = data.find { |row| row["CityName"].downcase == target_name }
      city_id = matched_row["CityID"]
      edit_url = "#{EDIT_OFFICIALS_URL}?cityID=#{city_id}"

      puts "Edit URL: #{edit_url}"

      { type: "url", data: edit_url }
    end

    def self.fetch(municipality_context)
      municipality_entry = municipality_context[:municipality_entry]

      puts "Scraping #{municipality_entry["name"]} officials from state source: mrsc"
      source_url = get_source_url(municipality_entry)

      # Check cache first
      if @@html_cache[municipality_entry["name"]]
        puts "Cache hit for #{municipality_entry["name"]}."
      else
        puts "Cache miss for #{municipality_entry["name"]}. Fetching from URL..."
        response = HTTParty.get(source_url)
        @@html_cache[municipality_entry["name"]] = response.body
      end

      # Use cached or newly fetched HTML
      html_string = @@html_cache[municipality_entry["name"]]

      parse_officials(municipality_entry, html_string)
    end

    def self.parse_officials(municipality_entry, html_string)
      html_doc = Nokogiri::HTML(html_string)
      municipality_name = municipality_entry["name"]

      # Replace underscores with spaces before lowercasing
      municipality_name_with_spaces = municipality_name.gsub("_", " ")
      lowercase_municipality_name = municipality_name_with_spaces.downcase

      puts "Searching for municipality: #{municipality_name} (normalized as #{lowercase_municipality_name})"
      officials = []
      parent_div = nil

      # Select all potential parent divs
      candidate_divs = html_doc.xpath("//div[@data-role='collapsible']")

      # Iterate in Ruby to find the correct div case-insensitively
      candidate_divs.each do |div|
        h3 = div.at_xpath("./h3")
        next unless h3

        # Get the node containing the city name (a or h3)
        municipality_name_node = h3.at_xpath("./a") || h3
        # Get text content of *only* that node, ignoring children like span
        h3_text_content = municipality_name_node.content

        # Normalize whitespace and case for comparison
        normalized_h3_text = h3_text_content.gsub(/\s+/, " ").strip.downcase
        # Normalize the target name (already has spaces instead of _, and is lowercase)
        normalized_municipality_name = lowercase_municipality_name.gsub(/\s+/, " ").strip

        if normalized_h3_text == normalized_municipality_name
          parent_div = div
          break # Found the correct div
        end
      end

      unless parent_div
        puts "ERROR: Could not find parent div for municipality '#{municipality_name}' after checking #{candidate_divs.count} candidates."
        return []
      end

      # Select direct children divs of parent_div that contain a <strong> tag
      people_divs_xpath = "./div[strong]"
      people_divs = parent_div.xpath(people_divs_xpath)

      puts "Found #{people_divs.count} people divs for #{municipality_name}:"
      people_divs.each do |person_div|
        name = person_div.at_xpath("./strong")&.text&.strip
        title = person_div.at_xpath("./span[1]")&.text&.strip # Assumes title is the first span
        email = person_div.at_xpath('.//a[starts-with(@href, "mailto:")]')&.text&.strip

        officials << {
          "name" => name.gsub(/\s+/, " ").strip,
          "positions" => title ? [title] : [], # Handle cases where title might be missing
          "email" => email
        }
      end

      officials
    end
  end
end
