module Scrapers::States::Wa::LocalOfficialScraper
  class StateLevelScraper
    DIRECTORY_URL = "https://mrsc.org/mrsctools/officials-directory/city.aspx".freeze
    @@html_cache ||= {}

    def self.source_url(city_entry)
      city_initial = city_entry["name"][0]
      "#{DIRECTORY_URL}?ci=#{city_initial}"
    end

    def self.get_officials(municipality_context)
      city_entry = municipality_context[:city_entry]

      puts "Scraping #{city_entry["name"]} officials from state source: mrsc"
      source_url = source_url(city_entry)

      # Check cache first
      if @@html_cache[city_entry["name"]]
        puts "Cache hit for #{city_entry["name"]}."
      else
        puts "Cache miss for #{city_entry["name"]}. Fetching from URL..."
        response = HTTParty.get(source_url)
        @@html_cache[city_entry["name"]] = response.body
      end

      # Use cached or newly fetched HTML
      html_string = @@html_cache[city_entry["name"]]

      parse_officials(city_entry, html_string)
    end

    def self.parse_officials(city_entry, html_string)
      html_doc = Nokogiri::HTML(html_string)
      city_name = city_entry["name"]

      # Replace underscores with spaces before lowercasing
      city_name_with_spaces = city_name.gsub("_", " ")
      lowercase_city_name = city_name_with_spaces.downcase

      puts "Searching for city: #{city_name} (normalized as #{lowercase_city_name})"
      officials = []
      parent_div = nil

      # Select all potential parent divs
      candidate_divs = html_doc.xpath("//div[@data-role='collapsible']")

      # Iterate in Ruby to find the correct div case-insensitively
      candidate_divs.each do |div|
        h3 = div.at_xpath("./h3")
        next unless h3

        # Get the node containing the city name (a or h3)
        city_name_node = h3.at_xpath("./a") || h3
        # Get text content of *only* that node, ignoring children like span
        h3_text_content = city_name_node.content

        # Normalize whitespace and case for comparison
        normalized_h3_text = h3_text_content.gsub(/\s+/, " ").strip.downcase
        # Normalize the target name (already has spaces instead of _, and is lowercase)
        normalized_city_name = lowercase_city_name.gsub(/\s+/, " ").strip

        if normalized_h3_text == normalized_city_name
          parent_div = div
          break # Found the correct div
        end
      end

      unless parent_div
        puts "ERROR: Could not find parent div for city '#{city_name}' after checking #{candidate_divs.count} candidates."
        return []
      end

      # Select direct children divs of parent_div that contain a <strong> tag
      people_divs_xpath = "./div[strong]"
      people_divs = parent_div.xpath(people_divs_xpath)

      puts "Found #{people_divs.count} people divs for #{city_name}:"
      people_divs.each do |person_div|
        name = person_div.at_xpath("./strong")&.text&.strip
        title = person_div.at_xpath("./span[1]")&.text&.strip # Assumes title is the first span
        email = person_div.at_xpath('.//a[starts-with(@href, "mailto:")]')&.text&.strip

        officials << {
          "name" => name,
          "positions" => title ? [title] : [], # Handle cases where title might be missing
          "email" => email
        }
      end

      officials
    end
  end
end
