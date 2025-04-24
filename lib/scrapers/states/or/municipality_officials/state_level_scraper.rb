module Scrapers::Or::MunicipalityOfficials
  class StateLevelScraper
    MUNICIPALITY_DIRECTORY_URL = "https://www.orcities.org/resources/reference/city-directory".freeze

    def self.fetch(municipality_context)
      key = municipality_context[:city_entry]["name"].downcase.gsub(" ", "-")
      url = "#{MUNICIPALITY_DIRECTORY_URL}/details/#{key}"
      response = HTTParty.get(url)
      html = Nokogiri::HTML(response.body)

      File.write("html.html", html)
      parse_html(html)
    end

    def self.parse_html(html)
      officials_div = html.at_xpath("//div[@class='city-info']")
      officials_div.xpath(".//h3[contains(text(), 'Elected Officials')]").each do |h3|
        h3.xpath(".//a").each do |a|
          puts a.text
        end
      end
    end
  end
end
