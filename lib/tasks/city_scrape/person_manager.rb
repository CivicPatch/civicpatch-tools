module CityScrape
  class PersonManager
    def self.fetch_people_info(state, gnis)
      data_fetcher = Scrapers::DataFetcher.new
      openai_service = Services::Openai.new

      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)

      raise "City entry not found for #{gnis} in #{state}" unless city_entry.present?

      city_data = CityScrape::CityManager.get_city_directory(state, city_entry)
      city_path = CityScrape::CityManager.get_city_path(state, city_entry)

      city_data["people"] = city_data["people"].map.with_index do |existing_person, index|
        website = Scrapers::Standard.get_website(existing_person)

        next existing_person unless website.present? && Scrapers::Common.missing_contact_info?(existing_person)

        puts "Processing #{existing_person["name"]}"
        candidate_dir = File.join(city_path, "city_scrape_sources", "member_info_#{index}")
        FileUtils.mkdir_p(candidate_dir)
        content_file = data_fetcher.extract_content(website, candidate_dir)
        person_info = openai_service.extract_person_information(content_file, website)

        next existing_person unless person_info.present? && person_info.is_a?(Hash)

        CityScrape::CityManager.merge_person(existing_person, person_info)
      end

      File.write(CityScrape::CityManager.get_city_directory_file(state, city_entry), city_data.to_yaml)

      # Copy images to <city_path>/images
      images_dir = File.join(city_path, "images")
      Dir.glob(File.join(city_path, "city_scrape_sources", "member_info_*", "images", "*")).each do |file|
        FileUtils.cp_r(file, images_dir, remove_destination: true)
      end

      CityScrape::StateManager.update_state_places(state, [
                                                     { "gnis" => city_entry["gnis"],
                                                       "last_member_info_scrape_run" => Time.now.strftime("%Y-%m-%d") }
                                                   ])
      Scrapers::Common.prune_unused_images(state, city_entry)
    end
  end
end
