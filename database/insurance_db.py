import sqlite3

def init_db(db_path="insurance.db"):
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          age INTEGER NOT NULL,
          state TEXT NOT NULL,
          vehicle_name TEXT NOT NULL,
          coverage_type TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          updated_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now'))
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS curriculum_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER NOT NULL UNIQUE,
          customer_age INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          updated_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS curriculum_modules (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          plan_id INTEGER NOT NULL,
          module_order INTEGER NOT NULL,
          module_title TEXT NOT NULL,
          module_description TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          UNIQUE(plan_id, module_order),
          FOREIGN KEY (plan_id) REFERENCES curriculum_plans(id) ON DELETE CASCADE
        );
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_curriculum_plans_customer_id ON curriculum_plans(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_curriculum_modules_plan_id ON curriculum_modules(plan_id);")