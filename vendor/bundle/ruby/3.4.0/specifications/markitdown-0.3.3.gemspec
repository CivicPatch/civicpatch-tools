# -*- encoding: utf-8 -*-
# stub: markitdown 0.3.3 ruby lib

Gem::Specification.new do |s|
  s.name = "markitdown".freeze
  s.version = "0.3.3".freeze

  s.required_rubygems_version = Gem::Requirement.new(">= 0".freeze) if s.respond_to? :required_rubygems_version=
  s.require_paths = ["lib".freeze]
  s.authors = ["Christopher Petersen".freeze]
  s.date = "2013-08-25"
  s.description = "A library that uses Nokogiri to parse HTML and produce Markdown".freeze
  s.email = ["chris@petersen.io".freeze]
  s.homepage = "https://github.com/cpetersen/markitdown".freeze
  s.licenses = ["MIT".freeze]
  s.rubygems_version = "1.8.23".freeze
  s.summary = "Converts HTML to Markdown".freeze

  s.installed_by_version = "3.6.2".freeze

  s.specification_version = 3

  s.add_runtime_dependency(%q<nokogiri>.freeze, [">= 0".freeze])
  s.add_development_dependency(%q<rake>.freeze, [">= 0".freeze])
  s.add_development_dependency(%q<rspec>.freeze, [">= 0".freeze])
  s.add_development_dependency(%q<coveralls>.freeze, [">= 0".freeze])
end
