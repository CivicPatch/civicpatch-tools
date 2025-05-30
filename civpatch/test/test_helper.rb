# frozen_string_literal: true

$LOAD_PATH.unshift File.expand_path("../lib", __dir__)
require "open_data"

require "minitest/autorun"
require "minitest/pride" # For colored output
require "yaml"
require "active_support/all"
