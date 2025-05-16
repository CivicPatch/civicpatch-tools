module Services
  class Requests
    def with_progress_indicator
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

    def with_model_fallback
      retry_attempts = 0
      current_model = MODELS[retry_attempts]

      begin
        yield(current_model)
      rescue Net::ReadTimeout => e
        return raise e if retry_attempts >= MAX_RETRIES

        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
        puts "Timeout with #{current_model}. Falling back to next model in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        current_model = MODELS[retry_attempts] || MODELS.last
        retry
      end
    end
  end
end
