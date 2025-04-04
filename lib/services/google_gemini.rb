module Services
  class GoogleGemini
    MODEL = "gemini-2.5-pro-exp-03-25".freeze
    BASE_URI = "https://generativelanguage.googleapis.com".freeze
    BASE_SLEEP = 5

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def get_city_directory(city, url)
      prompt = %(
        Give me city officials contact info for
        #{city} using #{url} Do this in YAML.

        Notes:
        * Return the values in YAML.
        * Don't return anything that isn't in YAML.
        * Don't list council members whose terms have ended.

        The YAML should be in this format, in an array:
        - name: <string>
          phone_number: <string> Format: (123) 456-7890
          email: <string>
          positions: [<an array of strings>]
          website:
          start_term_date: <string> Format: YYYY, YYYY-MM, or YYYY-MM-DD
          end_term_date: <string> Format: YYYY, YYYY-MM, or YYYY-MM-DD
      )

      response = run_prompt(prompt)
      response.map do |person|
        person["sources"] = [url]
        Scrapers::Standard.normalize_source_person(person)
      end
    end

    def run_prompt(prompt)
      retry_attempts = 0
      url = "#{BASE_URI}/v1beta/models/#{MODEL}:generateContent?key=#{@api_key}"

      payload = {
        contents: [{
          parts: [{
            text: prompt
          }]
        }]
      }.to_json

      options = {
        body: payload,
        headers: {
          "Content-Type" => "application/json"
        },
        timeout: 60
      }

      response = nil
      progress_thread = Thread.new do
        loop do
          print "."
          sleep 2
        end
      end

      begin
        response = HTTParty.post(url, options)
      ensure
        progress_thread.kill
        puts "\n" # Add a newline after the dots
      end

      if response.success?
        # TODO: needs more robustness
        response_candidate = response["candidates"].first
        yaml_string = response_candidate["content"]["parts"].first["text"]

        Utils::YamlHelper.yaml_string_to_hash(yaml_string)
      else
        puts "Request failed. HTTP Status: #{response.code}"
        nil
      end
    rescue StandardError => e
      puts e.message
      if retry_attempts < MAX_RETRIES
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
        puts "Might be running into rate limits. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "Too many requests. Max retries reached for Google Gemini."
      end
    end
  end
end
