# lib/tasks/convert_shapefile.rake
namespace :map do
  desc "Convert shapefile to GeoJSON"
  task :generate, [ :state, :type ] => :environment do |t, args|
    state = args[:state]
    type = args[:type] # can be places or cds

    if state.blank? || type.blank?
      puts "Error: State and type are required"
      exit 1
    end

    if type != "places" && type != "cds"
      puts "Error: Type must be places or cds"
      exit 1
    end

    state_info_file = Rails.root.join("data", "maps", state, "state_info.yml")
    state_info = YAML.load_file(state_info_file)

    if !File.exist?(state_info_file)
      puts "Error: State info file not found at #{state_info_file}"
      exit 1
    end

    # Ensure GDAL is installed and accessible
    unless system("ogr2ogr --version")
      puts "Error: GDAL is not installed or not in your PATH."
      exit 1
    end

    # find census shp file
    input_shp = Rails.root.join("data", "maps", state, state_info["#{type}_file"])
    destination_file = Rails.root.join("data", "maps", state, "census", "#{state}_#{type}.geojson")

    # Run the conversion command
    output_file = Rails.root.join("#{state}_#{type}.geojson")
    command = "ogr2ogr -f GeoJSON #{output_file} #{input_shp}"

    if system(command)
      FileUtils.mv(output_file, destination_file)
      puts "Conversion successful: #{destination_file}"
    else
      puts "Error: Conversion failed."
    end
  end

  task :sync, [ :state, :type ] => :environment do |t, args|
    state = args[:state]
    type = args[:type] # can be places or cds

    if state.blank? || type.blank?
      puts "Error: State and type are required"
      exit 1
    end

    if type != "places" && type != "cds"
      puts "Error: Type must be places or cds"
      exit 1
    end

    # get the geojson file
    geojson_file = Rails.root.join("data", "maps", state, "census", "#{state}_#{type}.geojson")

    # remove
  end
end
