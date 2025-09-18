env "local" {
  url = "sqlite://data/database.db"
  dev = "sqlite://data/tmp_database.db"
  schema {
    src = "file://database_operations/schema.sql"
  }
  migration {
    dir = "file://database_operations/migrations"
    baseline = "20250918040115"
  }
  format {
    schema {
      inspect = "{{ sql . \"  \" }}"
    }
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }
}