from auth import hash_string

def maybe_init_db(db_connection, db_cursor):
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            server_url TEXT,
            UNIQUE(provider, provider_user_id)
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'github',
            provider_user_id TEXT NOT NULL,
            api_key_suffix TEXT NOT NULL,
            api_key_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            revoked_at TIMESTAMP,
            FOREIGN KEY (provider, provider_user_id) REFERENCES users(provider, provider_user_id)
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER,
            action TEXT NOT NULL,
            type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
        )
    """)
    db_connection.commit()

def maybe_insert_user(db_connection, db_cursor, provider, provider_user_id, email):
  db_cursor.execute("""
      INSERT OR IGNORE INTO users (provider, provider_user_id, email)
      VALUES (?, ?, ?)
  """, (provider, provider_user_id, email))
  db_connection.commit()

def create_api_key(db_connection, db_cursor, provider, provider_user_id, database_hash_key):
    import secrets
    api_key = secrets.token_urlsafe(32)
    # Hash the API key before storing
    api_key_hash = hash_string(api_key, database_hash_key)
    api_key_suffix = api_key[-4:]

    db_cursor.execute("""
        INSERT INTO api_keys (provider, provider_user_id, api_key_hash, api_key_suffix)
        VALUES (?, ?, ?, ?)
    """, (provider, provider_user_id, api_key_hash, api_key_suffix))
    db_connection.commit()
    return api_key

def revoke_api_key(db_connection, db_cursor, api_key_id):
    db_cursor.execute("""
        UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (api_key_id,))
    db_connection.commit()

def get_api_keys_for_user(db_cursor, provider, provider_user_id):
    db_cursor.execute("""
        SELECT id, api_key_suffix, created_at, revoked_at FROM api_keys
        WHERE provider_user_id = ? AND provider = ?
    """, (provider_user_id, provider))
    rows = db_cursor.fetchall()
    return [
        {
            "id": row[0],
            "suffix": row[1],
            "created_at": row[2],
            "revoked_at": row[3],
        }
        for row in rows
    ]

def get_user_details(db_cursor, provider, provider_user_id):
    db_cursor.execute("""
        SELECT server_url, email FROM users
        WHERE provider_user_id = ? AND provider = ?
    """, (provider_user_id, provider))
    row = db_cursor.fetchone()
    if row:
        return {
            "server_url": row[0],
            "user_email": row[1],
        }
    return None

def is_active_api_key(db_cursor, database_hash_key, api_key) -> bool:
    candidate_api_key_hash = hash_string(api_key, database_hash_key)
    db_cursor.execute("""
        SELECT id FROM api_keys
        WHERE api_key_hash = ? AND revoked_at IS NULL
    """, (candidate_api_key_hash,))
    row = db_cursor.fetchone()
    return row is not None

def get_server_detail_by_active_api_key(db_cursor, database_hash_key, api_key):
    candidate_api_key_hash = hash_string(api_key, database_hash_key)
    db_cursor.execute("""
        SELECT user_email, server_url FROM api_keys
        WHERE api_key_hash = ? AND revoked_at IS NULL
    """, (candidate_api_key_hash,))
    row = db_cursor.fetchone()
    if row:
        return {
            "user_email": row[0],
            "server_url": row[1],
        }
    return None
