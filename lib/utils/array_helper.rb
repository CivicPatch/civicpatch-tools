module Utils
  module ArrayHelper
    def self.interleave_arrays(arrays)
      max_length = arrays.map(&:length).max || 0

      return [] if max_length.zero?

      result = []
      (0...max_length).each do |i|
        arrays.each do |sub_array|
          result << sub_array[i] if i < sub_array.length
        end
      end

      result
    end
  end
end
