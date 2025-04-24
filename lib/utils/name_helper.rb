module Utils
  class NameHelper
    def self.valid_name?(name)
      name.present? && name.strip.length.positive? && name.split(" ").length > 1
    end
  end
end
