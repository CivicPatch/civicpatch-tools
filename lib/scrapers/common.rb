# frozen_string_literal: true

module Scrapers
  module Common
    def self.fetch_places_from_wikipedia(state, title)
      response = fetch_with_wikipedia(title)
      nokogiri_doc = Nokogiri::HTML(response)
      table = nokogiri_doc.css("table.wikitable.sortable")[0]

      city_rows = table.css("tr")

      parse_cities_from_wikipedia_table(state, city_rows[3..])
    end

    def self.parse_cities_from_wikipedia_table(state, table_rows)
      places = []
      table_rows.css("tr").each do |city_row|
        columns = city_row.css("td, th")
        city_name = format_name(columns[0].text)
        city_type = format_name(columns[1].text)
        county_names = without_superscripts(columns[2]).text.split(",").map { |county| format_name(county) }
        city_link = columns[0].css("a")[0].attr("href")

        city_page_title = city_link.split("/").last
        city_population = columns[3].text.gsub(/[^\d]/, "").to_i

        puts "Fetching city page for #{city_name}"

        city_website, fips, gnis = fetch_city_page(city_page_title)

        place = {
          "ocd_ids" => generate_ocd_ids(state, county_names, city_name),
          "name" => city_name,
          "counties" => county_names,
          "website" => city_website,
          "fips" => fips,
          "gnis" => gnis,
          "type" => city_type,
          "population" => city_population
        }

        places << place
      end

      places
    end

    def self.generate_ocd_ids(state, county_names, city_name)
      ocd_ids = [
        "ocd-division/country:us/state:#{state}/place:#{city_name}"
      ]

      county_names.each do |county_name|
        ocd_ids << "ocd-division/country:us/state:#{state}/county:#{county_name}/place:#{city_name}"
      end

      ocd_ids
    end

    def self.fetch_with_wikipedia(title)
      url = "https://en.wikipedia.org/api/rest_v1/page/html/#{title}"
      response = HTTParty.get(url)

      raise "Error: #{response.code}" unless response.success?

      response.parsed_response
    end

    def self.fetch_city_page(wikipedia_title)
      response = fetch_with_wikipedia(wikipedia_title)
      nokogiri_doc = Nokogiri::HTML(response)

      infobox = nokogiri_doc.css("table.infobox")
      # find tr with th that has a td that contains "website"
      # then find the a tag within that tr that has a href attribute
      website_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("website") }
      website = website_row.present? ? website_row.css("a").find { |a| a.attr("href") } : nil
      website = website ? Scrapers::Common.format_url(website.attr("href")) : ""

      fips_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("fips") }
      fips = fips_row.present? ? without_superscripts(fips_row.css("td")).text : ""

      gnis_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("gnis") }
      gnis = gnis_row.present? ? without_superscripts(gnis_row.css("td")).text : ""

      [website, fips, gnis]
    end

    def self.without_superscripts(nokogiri_doc)
      nokogiri_doc.css("sup").each(&:remove) # Remove <sup> elements entirely
      nokogiri_doc # Return the modified document
    end

    def self.sort_url_pairs(url_pairs, keyword_groups)
      grouped_urls = Hash.new { |hash, key| hash[key] = [] }

      url_pairs.each do |url, text|
        keyword_groups.each do |group_name, keywords|
          if keywords.any? { |keyword| text.downcase.include?(keyword.downcase) }
            grouped_urls[group_name] << [url, text]
          end
        end
      end

      # Rank each url_pair by text, then by keywords in the url, and finally by url length
      grouped_urls.each do |group_name, pairs|
        grouped_urls[group_name] = pairs.sort_by do |url, text|
          [
            -score_text(text, keyword_groups[group_name]), # Rank by text score
            -keyword_count_in_url(url, keyword_groups[group_name]), # Rank by keyword count in URL
            url.length # Rank by URL length (shorter is better)
          ]
        end
      end

      # Interlace the sorted URLs from each group
      interlaced_results = []
      max_length = grouped_urls.values.map(&:size).max

      (0...max_length).each do |i|
        grouped_urls.each_value do |urls|
          interlaced_results << urls[i] if urls[i]
        end
      end

      interlaced_results.map { |url, _text| format_url(url) }.uniq
    end

    def self.format_url(url)
      # get rid of any trailing slashes
      url = url.gsub(%r{/$}, "")
      # get rid of any trailing spaces
      url = url.gsub(/\s+$/, "")
      # get rid of spaces
      url.gsub(" ", "%20")
    end

    def self.format_name(name)
      name = name.gsub("†", "")
      name = name.gsub("‡", "")
      # get rid of trailing spaces
      name = name.gsub(/\s+$/, "")
      # convert to key-friendly format
      name = name.gsub(" ", "_").downcase

      # get weird of wikipedia symbols
      name.gsub(" ", "_")
    end

    def self.score_text(text, keywords)
      score = 0
      keywords.each_with_index do |keyword, index|
        if text.downcase.include?(keyword.downcase)
          # Multiply by (keywords.size - index) to prioritize earlier keywords
          score += (keywords.size - index) * (keywords.size - index)
        end
      end
      score
    end

    def self.keyword_count_in_url(url, keywords)
      keywords.count { |keyword| url.downcase.include?(keyword.downcase.gsub(/[-_]/, "")) }
    end

    def self.urls_without_segments(urls, segments)
      urls.select do |url|
        url_segments = url.split("/").map(&:downcase)
        url_segments.none? { |segment| segments.include?(segment) }
      end
    end

    def self.get_ocd_parts(ocd_id)
      parts = ocd_id.split("/")
      hash = {}
      parts.each do |part|
        key, value = part.split(":")
        hash[key] = value if value
      end

      hash
    end
  end
end
