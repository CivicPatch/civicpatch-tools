module Services
  class Openai
    @@MAX_TOKENS = 9400

    def initialize
      @client = OpenAI::Client.new(access_token: Rails.application.credentials.openai_token)
    end

    def extract_city_division_map_data(state, city, division_type, geojson_file_path, url)
      truncated_geojson  = extract_simplified_geojson(geojson_file_path)
      truncated_geojson_text = truncated_geojson.to_json

      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor. The following is #{truncated_geojson.length} of the features of a geojson file.
        Determine if the following content contains #{truncated_geojson.length} city council #{division_type}s.

        If available, determine the following properties strictly in YAML format:
        - has_division_data ("true" or "false" -- true if the data set has the city's #{division_type} info)
        - has_city_data ("true" or "false" -- true if based off the page url and the data, that the dataset is for #{city}, #{state})
      INSTRUCTIONS

      user_instructions = <<~USER
        * This is the data: #{truncated_geojson_text}.
        * The city is split into #{division_type}s, and are more generically called "wards" or "districts".
        * The page url is: #{url}
        * Return the results in YAML format.

      USER

      if system_instructions.split(" ").length + user_instructions.split(" ").length > @@MAX_TOKENS
        raise "Extract city division map data: system instructions and user instructions are too long"
      end

      puts "system_instructions: #{system_instructions}"
      puts "user_instructions: #{user_instructions}"

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]

      response = run_prompt(messages)
      response_yaml = response_to_yaml(response)

      response_yaml
    end

    def extract_city_info(state, city, content_file, city_council_url)
      content = File.read(content_file)

      if content.split(" ").length > @@MAX_TOKENS
        raise "Content for city council members is too long"
      end

      system_instructions, user_instructions = generate_city_info_prompt(content, city_council_url)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      response_yaml = run_prompt(messages)

      response_to_yaml(response_yaml)
    end

    def response_to_yaml(response_content)
      # Extract YAML content from the response
      # If the response is wrapped in ```yaml ... ``` or similar, extract just the YAML content
      yaml_content = if response_content.match?(/```(?:yaml|yml)?\s*(.*?)```/m)
        response_content.match(/```(?:yaml|yml)?\s*(.*?)```/m)[1]
      else
        response_content
      end

      YAML.load(yaml_content)
    end

    def generate_city_info_prompt(content, city_council_url)
      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
      You are an expert data extractor.
      Extract the following properties from the provided content:

      For each council member (leave empty if not found):
        - council_members:
            - name
            - phone_number
            - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL.)
            - email
            - website (Provide the absolute URL.)
              If no specific website is provided, leave this empty — do not default to the general city or council page.)

      For each city leader (e.g., mayors, city managers, etc. leave empty if not found):
        - city_leaders:
            - name
            - position (e.g., Mayor, City Manager, etc.)
            - phone_number
            - image (Same rules as above.)
            - email
            - website (Same rules as above.)

      Basic rules:
      - Youth council members are NOT city council members.
      - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
      - If you find just a list of names, with at least a website or email, they are likely to be council members.
      - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
      - If you cannot find any relevant information, return the following YAML:
        - error: "No relevant information found"

      Example Output (YAML):
      ---
      council_members:
        - name: "Jane Smith"
          phone_number: "555-123-4567"
          image: "images/smith.jpg"
          email: "jsmith@cityofexample.gov"
          website: "https://www.cityofexample.gov/council/smith"
        - name: "John Doe"
          phone_number: ""
          image: ""
          email: ""
          website: "/council/doe"
      city_leaders:
        - name: "Robert Johnson"
          position: "Mayor"
          phone_number: "555-111-2222"
          image: "images/mayor.jpg"
          email: "mayor@cityofexample.gov"
          website: "https://www.cityofexample.gov/mayor"

      INSTRUCTIONS

      content = <<~CONTENT
        #{content}
      CONTENT

      # User instructions: approximately 40 tokens (excluding the HTML content)
      user_instructions = <<~USER
        The page URL is: #{city_council_url}
        Here is the content:
        #{content}
      USER

      [ system_instructions, user_instructions ]
    end

    private

    def run_prompt(messages)
      response = @client.chat(
        parameters: {
            model: "gpt-4o-mini",
            # model: "gpt-3.5-turbo",
            messages: messages,
            temperature: 0.0
        }
      )

      response.dig("choices", 0, "message", "content")
    end

    # Remove coordinates from geojson file
    def extract_simplified_geojson(geojson_file_path)
      file_size_mb = File.size(geojson_file_path) / 1024.0 / 1024.0
      puts "Loading geojson file - #{file_size_mb} MB"

      json_data = JSON.parse(File.read(geojson_file_path))

      features = json_data["features"][0, 3].map do |feature|
        {
          type: feature["type"],
          properties: feature["properties"]
        }
      end

      features
    end
  end
end
