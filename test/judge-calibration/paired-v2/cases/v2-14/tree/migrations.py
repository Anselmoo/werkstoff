def add_status_column():
    return "ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'new'"
