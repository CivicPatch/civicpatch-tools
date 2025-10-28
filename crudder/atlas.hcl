env "local" {
  url = getenv("HOST_CRUDDER_DB_URL")
  dev = "docker+postgres://postgis/postgis/dev?search_path=public"
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
