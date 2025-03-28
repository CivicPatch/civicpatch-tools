require_relative "../scrapers/data_fetcher"
require_relative "../path_helper"
require_relative "../services/openai"

namespace :scratch do
  desc "Fetch data using Scrapers::DataFetcher"
  task :fetch  do |_t, args|
    url = "https://www.burienwa.gov/city_hall/city_council/deputy_mayor_stephanie_mora"
    destination_dir = PathHelper.project_path("./testing")

    begin
      fetcher = Scrapers::DataFetcher.new
      openai_service = Services::Openai.new
      result = fetcher.extract_content(url, destination_dir)
      response = openai_service.extract_city_info(result, url)

      puts "Successfully fetched data to: #{result}"
      puts "Response: #{response}"
    rescue StandardError => e
      puts "Error: #{e.message}"
      puts e.backtrace
      exit 1
    end
  end
end
