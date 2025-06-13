# frozen_string_literal: true

require "test_helper"
require "utils/phone_helper"

module Utils
  class PhoneHelperTest < Minitest::Test
    def test_nil_phone
      assert_nil PhoneHelper.format_phone_number(nil)
    end

    def test_empty_phone
      assert_nil PhoneHelper.format_phone_number("")
    end

    def test_whitespace_only_phone
      assert_nil PhoneHelper.format_phone_number("   ")
    end

    def test_too_short_phone
      assert_nil PhoneHelper.format_phone_number("123-456")
    end

    def test_standard_10_digit_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("5551234567")
    end

    def test_formatted_10_digit_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("(555) 123-4567")
    end

    def test_dashes_in_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("555-123-4567")
    end

    def test_spaces_in_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("555 123 4567")
    end

    def test_dots_in_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("555.123.4567")
    end

    def test_mixed_separators_in_phone
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("555.123-4567")
    end

    def test_us_number_with_country_code
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("15551234567")
    end

    def test_us_number_with_formatted_country_code
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number("+1 (555) 123-4567")
    end

    def test_international_number
      assert_equal "+447911123456", PhoneHelper.format_phone_number("+447911123456")
    end

    def test_extension_lowercase
      assert_equal "(555) 123-4567 ext. 890", PhoneHelper.format_phone_number("555-123-4567 ext 890")
    end

    def test_extension_uppercase
      assert_equal "(555) 123-4567 ext. 890", PhoneHelper.format_phone_number("555-123-4567 EXT 890")
    end

    def test_extension_mixed_case
      assert_equal "(555) 123-4567 ext. 890", PhoneHelper.format_phone_number("555-123-4567 Ext 890")
    end

    def test_x_extension
      assert_equal "(555) 123-4567 ext. 890", PhoneHelper.format_phone_number("555-123-4567 x 890")
    end

    def test_x_extension_uppercase
      assert_equal "(555) 123-4567 ext. 890", PhoneHelper.format_phone_number("555-123-4567 X 890")
    end

    def test_array_phone_number
      assert_equal "(555) 123-4567", PhoneHelper.format_phone_number(%w[555-123-4567 555-987-6543])
    end
  end
end
