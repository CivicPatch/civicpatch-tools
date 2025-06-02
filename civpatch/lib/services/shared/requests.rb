module Services
  module Shared
    class Requests
      MAX_RETRIES = 5 # Maximum retry attempts for rate limits
      BASE_SLEEP = 5 # Base sleep time in seconds for exponential backoff

      def self.with_progress_indicator
        progress_thread = Thread.new do
          loop do
            print "."
            sleep 2
          end
        end
        yield
      ensure
        progress_thread.kill
        puts
      end

      def self.with_model_fallback(models)
        retry_attempts = 0
        current_model = models[retry_attempts]

        begin
          yield(current_model)
        rescue StandardError => e
          return raise e if retry_attempts >= MAX_RETRIES

          sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
          puts "Error with #{current_model}: #{e.message}"
          puts "Error with #{current_model}. Falling back to next model in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
          sleep sleep_time
          retry_attempts += 1
          current_model = models[retry_attempts] || models.last
          retry
        end
      end
    end
  end
end
