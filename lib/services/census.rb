module Services
  class Census
    STATE_TO_STATEFP = {
      "or" => "41",
      "wa" => "53"
    }.freeze

    PLACE_MAP_URL = "https://www2.census.gov/geo/tiger/TIGER2024/PLACE"

    def self.download_municipalities(state)
      statefp = STATE_TO_STATEFP[state]
      url = "#{PLACE_MAP_URL}/tl_2024_#{statefp}_place.zip"

      outfile = Tempfile.new(binmode: true)
      HTTParty.get(url) do |fragment|
        next if [301, 302].include?(fragment.code)

        outfile.write(fragment)
      end

      dest_dir = PathHelper.project_path(File.join("data", state, ".maps", "place_2024"))

      FileUtils.mkdir_p(dest_dir)

      # Unzip to data_source/<state>/.maps/place_2024
      Zip::File.open(outfile.path) do |zip_file|
        zip_file.each do |entry|
          entry.extract(File.join(dest_dir, entry.name))
        end
      end
    end
  end
end
