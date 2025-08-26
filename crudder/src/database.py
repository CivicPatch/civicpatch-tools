def maybe_init_db(db_connection, db_cursor):
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            server_name TEXT,
            server_url TEXT,
            UNIQUE(provider, provider_user_id)
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'github',
            provider_user_id TEXT NOT NULL,
            api_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            revoked_at TIMESTAMP,
            FOREIGN KEY (provider, provider_user_id) REFERENCES users(provider, provider_user_id)
        )
    """)
    db_cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_name TEXT,
            api_key_id INTEGER,
            action TEXT NOT NULL,
            type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
        )
    """)
    db_connection.commit()

def maybe_insert_user(db_connection, db_cursor, provider, provider_user_id):
  db_cursor.execute("""
      INSERT OR IGNORE INTO users (provider, provider_user_id)
      VALUES (?, ?)
  """, (provider, provider_user_id))
  db_connection.commit()

def create_api_key(db_connection, db_cursor, provider, provider_user_id):
    import secrets
    api_key = secrets.token_urlsafe(32)
    db_cursor.execute("""
        INSERT INTO api_keys (provider, provider_user_id, api_key)
        VALUES (?, ?, ?)
    """, (provider, provider_user_id, api_key))
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
        SELECT id, api_key, created_at, revoked_at FROM api_keys
        WHERE provider_user_id = ? AND provider = ?
    """, (provider_user_id, provider))
    rows = db_cursor.fetchall()
    return [
        {
            "id": row[0],
            "suffix": row[1][-4:],
            "created_at": row[2],
            "revoked_at": row[3],
        }
        for row in rows
    ]

def get_user_details(db_cursor, provider, provider_user_id):
    db_cursor.execute("""
        SELECT server_name, server_url FROM users
        WHERE provider_user_id = ? AND provider = ?
    """, (provider_user_id, provider))
    row = db_cursor.fetchone()
    if row:
        return {
            "server_name": row[0],
            "server_url": row[1],
        }
    return None