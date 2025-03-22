# lib/tasks/convert_shapefile.rake
namespace :map do
  desc "Convert shapefile to GeoJSON"
  task :generate, [ :state, :type ] do |t, args|
    state = args[:state]
    type = args[:type] # can be places or cds

    census_info = validate_generate_args(state, type)

    # Ensure GDAL is installed and accessible
    unless system("ogr2ogr --version")
      puts "Error: GDAL is not installed or not in your PATH."
      exit 1
    end

    # find census shp file
    input_shp = PathHelper.project_path(File.join("data", "us", "census", census_info["#{type}_file"]))
    destination_file = PathHelper.project_path(File.join("data", "us", state, "#{type}.geojson"))

    # Run the conversion command
    output_file = PathHelper.project_path("#{state}_#{type}.geojson")
    command = "ogr2ogr -f GeoJSON #{output_file} #{input_shp}"

    if system(command)
      FileUtils.mv(output_file, destination_file)
      puts "Conversion successful: #{destination_file}"
    else
      puts "Error: Conversion failed."
    end
  end

  private 

  def validate_generate_args(state, type)
    if state.blank? || type.blank?
      puts "Error: State and type are required"
      exit 1
    end

    census_info_file = PathHelper.project_path(File.join("data", "us", "census", "info.yml"))
    puts "census_info_file: #{census_info_file}"

    if !File.exist?(census_info_file)
      puts "Error: Census info file not found at #{census_info_file}"
      exit 1
    end

    census_info = YAML.load_file(census_info_file)
    census_info
  end
end
