# frozen_string_literal: true

require "nokogiri" # Explicitly require nokogiri

module Scrapers
  module Nh
    class Municipalities
      DIRECTORY_URL = "https://www.nhes.nh.gov/elmi/products/cp/"
      # Keywords to help identify the correct contact table
      CONTACT_TABLE_MAIN_KEYWORDS = ["community contact", "telephone"].freeze

      def self.fetch
        response = Browser.fetch_page_content(DIRECTORY_URL)
        directory_html_string = response[:page_html]
        unless directory_html_string
          puts "Failed to fetch NH Directory page at #{DIRECTORY_URL}"
          return []
        end
        directory_doc = Nokogiri::HTML(directory_html_string)

        municipality_page_infos = directory_doc.css("#CommProfiles option").map do |option|
          url_value = option["value"]
          decoded_url = Nokogiri::HTML.fragment(url_value).text # Decode &amp;
          {
            name: option.text.strip,
            url: decoded_url
          }
        end

        all_municipalities_data = municipality_page_infos.map do |page_info|
          pp page_info
          puts "Processing: #{page_info[:name]}"
          sleep 1
          scrape_page_details(page_info)
        end
        all_municipalities_data = all_municipalities_data.compact

        all_municipalities_data.each_with_object({}) do |m, hash|
          hash[m["name"]] = m
        end
      end

      def self.scrape_page_details(page_info)
        page_html_string = Browser.fetch_page_content(page_info[:url])
        unless page_html_string
          puts "Failed to fetch page for #{page_info[:name]} at #{page_info[:url]}"
          return { name: page_info[:name], url: page_info[:url], error: "Page fetch failed" }
        end
        page_doc = Nokogiri::HTML(page_html_string)

        contact_details = parse_contact_details(page_info, page_doc)
        government_type = parse_government_type(page_info, page_doc)

        {
          "name" => page_info[:name].to_s,
          **contact_details,
          "government_type" => government_type
        }
      end

      def self.parse_government_type(page_info, page_doc)
        government_table_row = page_doc.css("table.comtable tr").find do |row|
          row.css("td").any? do |cell|
            cell.text.strip.downcase.include?("type of government")
          end
        end

        if government_table_row.nil?
          puts "No government table row found for #{page_info[:name]} at #{page_info[:url]}"
          return nil
        end

        government_type = government_table_row.at_css("td.data").text.strip.downcase
        if government_type.blank?
          puts "No government type found for #{page_info[:name]} at #{page_info[:url]}"
          return nil
        end

        government_type
      end

      def self.parse_contact_details(page_info, page_doc)
        contact_table_node = page_doc.css("table.comtable").find do |table|
          first_column_texts = table.css("tr td:first-child").map { |td| td.text.strip.downcase }
          CONTACT_TABLE_MAIN_KEYWORDS.all? { |keyword| first_column_texts.include?(keyword) }
        end

        unless contact_table_node
          puts "Could not find a suitable contact table for #{page_info[:name]} at #{page_info[:url]}"
          return { name: page_info[:name], url: page_info[:url], error: "Contact table not found" }
        end

        details = {}
        current_community_contact_lines = [] # This will store the text from the 3rd TD of CC rows
        collecting_community_contact = false

        contact_table_node.css("tr").each do |row|
          cells = row.css("td")
          next if cells.empty?

          key_text = (cells[0] ? cells[0].text.strip : "")
          # value_text IS the content of the 3rd td (cells[2])
          value_text = (cells[2] ? cells[2].text.strip : "")

          key_empty = key_text.strip.empty? || key_text == "\u00A0"
          value_empty = value_text.strip.empty? || value_text == "\u00A0"

          current_key_normalized = key_text.downcase unless key_empty

          if current_key_normalized == "community contact"
            # Starting a Community Contact block
            if collecting_community_contact && !current_community_contact_lines.empty?
              # Finalize previous block if necessary (defensive)
              last_two_prev = current_community_contact_lines.last(2)
              details[:address] = last_two_prev.join("; ").strip unless last_two_prev.empty?
            end
            collecting_community_contact = true
            # Add the 3rd td's text from THIS row to start the new list
            current_community_contact_lines = [value_text].reject { |v| v.strip.empty? || v == "\u00A0" }
          elsif collecting_community_contact && key_empty
            # Continuation of Community Contact: add the 3rd td's text from THIS row
            current_community_contact_lines << value_text unless value_empty
          else
            # Not "Community Contact" or its continuation; current CC block ends
            if collecting_community_contact
              unless current_community_contact_lines.empty?
                # Take the 3rd td's text from the last two collected rows
                last_two = current_community_contact_lines.last(2)
                details[:address] = last_two.join("; ").strip unless last_two.empty?
              end
              current_community_contact_lines.clear
            end
            collecting_community_contact = false

            next if key_empty || value_empty

            case current_key_normalized
            when "telephone"
              details[:phone_number] = value_text # value_text is from 3rd td
            when "e-mail"
              details[:email] = value_text # value_text is from 3rd td
            when "web site"
              if value_text.match?(/\Awww\.|\.gov|\.com|\.org|\.net/i) && !value_text.match?(%r{N/A}i)
                processed_website = value_text # value_text is from 3rd td
                details[:website] = if processed_website
                                       .start_with?("http://", "https://")
                                      processed_website
                                    else
                                      "http://#{processed_website}"
                                    end
              end
            end
          end
        end

        # After loop, finalize if still collecting community contact
        if collecting_community_contact && !current_community_contact_lines.empty?
          last_two = current_community_contact_lines.last(2)
          details[:address] = last_two.join("; ").strip unless last_two.empty?
        end

        # Prepare final output, converting symbol keys from 'details' to strings
        final_data_hash = {}
        details.compact.each do |key, value|
          final_data_hash[key.to_s] = value
        end

        final_data_hash
      end
    end
  end
end
