# frozen_string_literal: true
require "nokogiri"
require "open-uri"
require "httparty"
require "json"
require 'yaml'
require 'active_support/core_ext/object/blank'
require 'active_support/core_ext/string' 
require 'active_support/core_ext/array' 


require "bundler/gem_tasks"
require "minitest/test_task"

require_relative "lib/path_helper"
require_relative "lib/open_data"

OpenData.load_tasks

Minitest::TestTask.create

require "rubocop/rake_task"

RuboCop::RakeTask.new

task default: %i[test rubocop]
