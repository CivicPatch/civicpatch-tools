module Scrapers
  class CityDirectory
    KEY_POSITIONS = ["Council Member",
                     "Mayor",
                     "Council President",
                     "Council Manager"].freeze

    COMMON_KEYWORDS = { name: "elected officials", keywords: [
      "elected officials", "index", "government", "bios", "meet", "about"
    ] }.freeze

    CITY_COUNCIL_KEYWORDS = { name: "council members",
                              keywords: [
                                "meet the council",
                                "city council members",
                                "mayor and city council",
                                "council bios",
                                "council districts",
                                "council members",
                                "councilmembers",
                                "city council",
                                "city hall",
                                "council"
                              ] }.freeze

    MAYOR_COUNCIL_KEYWORDS = [CITY_COUNCIL_KEYWORDS,
                              { name: "city leader", keywords: [
                                "mayor",
                                "meet the mayor",
                                "about the mayor",
                                "council president"
                              ] }, COMMON_KEYWORDS].freeze
  end
end
