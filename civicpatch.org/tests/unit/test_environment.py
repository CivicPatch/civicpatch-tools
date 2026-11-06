import environment


def test_pool_sizes_set_by_a_deployment_reach_get_pool(monkeypatch):
    monkeypatch.setenv("DB_POOL_MIN_SIZE", "1")
    monkeypatch.setenv("DB_POOL_MAX_SIZE", "10")

    env = environment.get_env_vars()

    assert (env["DB_POOL_MIN_SIZE"], env["DB_POOL_MAX_SIZE"]) == ("1", "10")


def test_pool_sizes_unset_fall_back_to_the_defaults(monkeypatch):
    monkeypatch.delenv("DB_POOL_MIN_SIZE")
    monkeypatch.delenv("DB_POOL_MAX_SIZE")

    env = environment.get_env_vars()

    assert (env["DB_POOL_MIN_SIZE"], env["DB_POOL_MAX_SIZE"]) == ("4", "20")
