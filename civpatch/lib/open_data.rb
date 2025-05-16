# frozen_string_literal: true

module OpenData
  class Error < StandardError; end
  # Your code goes here...

  def self.load_tasks
    require "rake"

    # Load all task files from the tasks directory
    Dir.glob(File.join(__dir__, "tasks", "*.rb")).each do |file|
      require file
    end
  end
end
