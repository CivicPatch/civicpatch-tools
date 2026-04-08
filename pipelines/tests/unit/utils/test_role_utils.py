import pytest
from utils.role_utils import people_with_roles

pytestmark = pytest.mark.unit

class DummyPerson:
    def __init__(self, role=None, roles=None):
        self.role = role
        self.roles = roles

def test_single_role_object():
    people = [DummyPerson(role="admin"), DummyPerson(role="user")]
    roles = ["admin"]
    result = people_with_roles(people, roles)
    assert len(result) == 1
    assert result[0].role == "admin"

def test_multiple_roles_object():
    people = [DummyPerson(roles=["admin", "editor"]), DummyPerson(roles=["user"])]
    roles = ["editor"]
    result = people_with_roles(people, roles)
    assert len(result) == 1
    assert "editor" in result[0].roles

def test_dict_roles():
    people = [{"roles": ["admin", "user"]}, {"role": "editor"}]
    roles = ["admin", "editor"]
    result = people_with_roles(people, roles)
    assert len(result) == 2
    assert result[0]["roles"] == ["admin", "user"]
    assert result[1]["role"] == "editor"

def test_empty_roles():
    people = [DummyPerson(role=None), {"roles": None}]
    roles = ["admin"]
    result = people_with_roles(people, roles)
    assert result == []

def test_no_matching_roles():
    people = [DummyPerson(role="user"), {"roles": ["viewer"]}]
    roles = ["admin"]
    result = people_with_roles(people, roles)
    assert result == []