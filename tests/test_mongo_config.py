from backend import mongo_config


def test_explicit_mongo_uri_wins(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://explicit")
    monkeypatch.setenv("MONGO_URI", "mongodb://fallback")

    assert mongo_config.get_mongo_uri() == "mongodb://explicit"


def test_mongo_uri_env_alias(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("MONGO_URI", "mongodb://alias")

    assert mongo_config.get_mongo_uri() == "mongodb://alias"


def test_atlas_uri_escapes_credentials(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.setenv("MONGO_TYPE", "atlas")
    monkeypatch.setenv("MONGO_USER", "user@example.com")
    monkeypatch.setenv("MONGO_PASS", "p@ss word")
    monkeypatch.setenv("MONGO_HOST_URI", "cluster.example.mongodb.net")
    monkeypatch.setenv("MONGO_DB_NAME", "guarded")
    monkeypatch.setenv("MONGO_AUTH_SRC", "admin db")
    monkeypatch.setenv("MONGO_W", "majority")
    monkeypatch.setenv("MONGO_APP_NAME", "Armor IQ")

    uri = mongo_config.get_mongo_uri()

    assert uri.startswith("mongodb+srv://user%40example.com:p%40ss+word@cluster.example.mongodb.net/")
    assert "authSource=admin+db" in uri
    assert "appName=Armor+IQ" in uri


def test_local_uri_default(monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("MONGO_TYPE", raising=False)
    monkeypatch.delenv("MONGO_LOCAL_URI", raising=False)

    assert mongo_config.get_mongo_uri() == "mongodb://localhost:27017"


def test_heartbeat_default_and_override(monkeypatch):
    monkeypatch.delenv("MONGO_HEARTBEAT_MS", raising=False)
    assert mongo_config.get_mongo_heartbeat_ms() == 60000

    monkeypatch.setenv("MONGO_HEARTBEAT_MS", "12345")
    assert mongo_config.get_mongo_heartbeat_ms() == 12345
