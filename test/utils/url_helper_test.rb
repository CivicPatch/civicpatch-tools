# frozen_string_literal: true

require "minitest/autorun"
require_relative "../../lib/utils/url_helper" # Adjust path as needed

class UrlHelperTest < Minitest::Test
  def test_removes_www_prefix
    assert_equal "https://example.com", Utils::UrlHelper.normalize_for_comparison("https://www.example.com")
  end

  def test_removes_trailing_slash
    assert_equal "http://example.com/path", Utils::UrlHelper.normalize_for_comparison("http://example.com/path/")
  end

  def test_removes_www_and_trailing_slash
    assert_equal "https://example.com/path", Utils::UrlHelper.normalize_for_comparison("https://www.example.com/path/")
  end

  def test_handles_url_without_www_or_trailing_slash
    assert_equal "http://example.com", Utils::UrlHelper.normalize_for_comparison("http://example.com")
  end

  def test_keeps_path
    assert_equal "https://example.com/some/path", Utils::UrlHelper.normalize_for_comparison("https://www.example.com/some/path")
  end

  def test_keeps_query_parameters
    # Addressable::URI normalize might reorder params, which is fine
    normalized = Utils::UrlHelper.normalize_for_comparison("https://www.example.com/path?b=2&a=1")
    assert_equal "https://example.com/path?a=1&b=2", normalized
  end

  def test_keeps_fragment
    assert_equal "https://example.com/path#section", Utils::UrlHelper.normalize_for_comparison("https://www.example.com/path#section")
  end

  def test_handles_nil_input
    assert_nil Utils::UrlHelper.normalize_for_comparison(nil)
  end

  def test_handles_non_http_scheme
    assert_equal "ftp://example.com/resource",
                 Utils::UrlHelper.normalize_for_comparison("ftp://www.example.com/resource")
  end

  def test_returns_original_on_parsing_error
    # Example of a potentially problematic URL (though Addressable might handle it)
    malformed_url = "http://[::1]:namedport"
    # We expect it to return the original string if Addressable::URI.parse fails internally
    # Note: Addressable is quite robust, finding a truly unparseable URL is tricky.
    # This test assumes the rescue block might be hit in some edge cases.
    # If Addressable *can* parse it, this test might need adjustment based on expected normalized output.
    assert_equal malformed_url, Utils::UrlHelper.normalize_for_comparison(malformed_url)
  end

  def test_handles_already_normalized_url
    url = "https://example.com/path?a=1#frag"
    assert_equal url, Utils::UrlHelper.normalize_for_comparison(url)
  end

  def test_handles_host_without_www
    assert_equal "https://subdomain.example.com", Utils::UrlHelper.normalize_for_comparison("https://subdomain.example.com")
  end
end
