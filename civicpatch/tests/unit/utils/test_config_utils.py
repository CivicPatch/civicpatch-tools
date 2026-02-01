import unittest
from unittest.mock import patch
from shared.utils.config_utils import get_role_alias_map

class TestGetRoleAliasMap(unittest.TestCase):

    @patch('shared.utils.config_utils.get_role_configs')
    def test_basic_functionality(self, mock_get_role_configs):
        mock_get_role_configs.return_value = [
            {"role": ["Mayor"], "aliases": ["Head of City", "City Leader"]},
            {"role": ["Council Member"], "aliases": ["CM", "Board Member"]}
        ]

        result = get_role_alias_map("mayor_council")
        expected = {
            "mayor": "Mayor",
            "head of city": "Mayor",
            "city leader": "Mayor",
            "council member": "Council Member",
            "cm": "Council Member",
            "board member": "Council Member"
        }
        self.assertEqual(result, expected)

    @patch('shared.utils.config_utils.get_role_configs')
    def test_empty_configuration(self, mock_get_role_configs):
        mock_get_role_configs.return_value = []

        result = get_role_alias_map("mayor_council")
        self.assertEqual(result, {})

    @patch('shared.utils.config_utils.get_role_configs')
    def test_case_insensitivity(self, mock_get_role_configs):
        mock_get_role_configs.return_value = [
            {"role": ["Mayor"], "aliases": ["Head of City"]}
        ]

        result = get_role_alias_map("mayor_council")
        self.assertEqual(result["mayor"], "Mayor")
        self.assertEqual(result["head of city"], "Mayor")
        self.assertEqual(result["HEAD OF CITY".lower()], "Mayor")

    @patch('shared.utils.config_utils.get_role_configs')
    def test_multiple_aliases(self, mock_get_role_configs):
        mock_get_role_configs.return_value = [
            {"role": ["Mayor"], "aliases": ["Head of City", "City Leader", "Chief"]}
        ]

        result = get_role_alias_map("mayor_council")
        self.assertEqual(result["head of city"], "Mayor")
        self.assertEqual(result["city leader"], "Mayor")
        self.assertEqual(result["chief"], "Mayor")

if __name__ == "__main__":
    unittest.main()
