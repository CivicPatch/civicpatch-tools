# frozen_string_literal: true

module Utils
  class FolderHelper
    def self.format_name(name)
      name.downcase.gsub(" ", "_")
    end
  end
end
