import sqlite3

def init_db(db_path="insurance.db"):
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
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

        conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_quiz_attempts (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          plan_id INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          module_order INTEGER,
          -- Newer fields used by the current app code
          questions_count INTEGER NOT NULL,
          points_possible REAL NOT NULL,
          points_earned REAL NOT NULL,
          -- Backward-compatible fields expected by tests/older callers
          questions_total INTEGER NOT NULL DEFAULT 0,
          questions_answered INTEGER NOT NULL DEFAULT 0,
          total_points REAL NOT NULL DEFAULT 0,
          earned_points REAL NOT NULL DEFAULT 0,
          mode TEXT NOT NULL DEFAULT 'question_bank',
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
          FOREIGN KEY (plan_id) REFERENCES curriculum_plans(id) ON DELETE CASCADE
        );
        """)

        try:
          conn.execute("ALTER TABLE knowledge_quiz_attempts ADD COLUMN questions_total INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
          pass
        try:
          conn.execute("ALTER TABLE knowledge_quiz_attempts ADD COLUMN module_order INTEGER;")
        except sqlite3.OperationalError:
          pass
        try:
          conn.execute("ALTER TABLE knowledge_quiz_attempts ADD COLUMN questions_answered INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
          pass
        try:
          conn.execute("ALTER TABLE knowledge_quiz_attempts ADD COLUMN total_points REAL NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
          pass
        try:
          conn.execute("ALTER TABLE knowledge_quiz_attempts ADD COLUMN earned_points REAL NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
          pass

        conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_quiz_results (
          id TEXT PRIMARY KEY,
          attempt_id TEXT NOT NULL,
          question_id TEXT NOT NULL,
          module_order INTEGER,
          question_type TEXT NOT NULL,
          weight REAL NOT NULL,
          answer_text TEXT,
          correct INTEGER NOT NULL,
          points_earned REAL NOT NULL,
          -- Backward-compatible alias expected by tests
          earned_points REAL NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          FOREIGN KEY (attempt_id) REFERENCES knowledge_quiz_attempts(id) ON DELETE CASCADE
        );
        """)
        try:
          conn.execute("ALTER TABLE knowledge_quiz_results ADD COLUMN earned_points REAL NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
          pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_kqa_customer ON knowledge_quiz_attempts(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kqa_plan ON knowledge_quiz_attempts(plan_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kqr_attempt ON knowledge_quiz_results(attempt_id);")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_validation_module_views (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          module_order INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kvmv_customer ON knowledge_validation_module_views(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kvmv_module ON knowledge_validation_module_views(customer_id, module_order);")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          module_order INTEGER,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          updated_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          status TEXT NOT NULL DEFAULT 'active',
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_cards (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          module_order INTEGER NOT NULL,
          module_title TEXT NOT NULL,
          front TEXT NOT NULL,
          back TEXT NOT NULL,
          difficulty TEXT NOT NULL DEFAULT 'easy',
          tags TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'new',
          attempts INTEGER NOT NULL DEFAULT 0,
          correct_count INTEGER NOT NULL DEFAULT 0,
          wrong_count INTEGER NOT NULL DEFAULT 0,
          last_answer TEXT,
          updated_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE
        );
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_sessions_customer ON quiz_sessions(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_cards_session ON quiz_cards(session_id);")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS teacher_module_views (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          module_order INTEGER NOT NULL,
          module_title TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_views_customer ON teacher_module_views(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_views_module ON teacher_module_views(customer_id, module_order);")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS accident_reports (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          updated_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          location TEXT,
          injured_count INTEGER NOT NULL DEFAULT 0,
          vehicles_drivable INTEGER,
          notes TEXT,
          evidence_urls TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'collecting',
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS severity_assessments (
          id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          severity TEXT NOT NULL,
          accident_type TEXT,
          urgency TEXT NOT NULL,
          rationale TEXT,
          recommended_actions TEXT NOT NULL DEFAULT '[]',
          FOREIGN KEY (report_id) REFERENCES accident_reports(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS policy_interpretations (
          id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          coverage_summary TEXT NOT NULL,
          estimated_deductible REAL,
          estimated_out_of_pocket REAL,
          assumptions TEXT NOT NULL DEFAULT '[]',
          exclusions TEXT NOT NULL DEFAULT '[]',
          FOREIGN KEY (report_id) REFERENCES accident_reports(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_packets (
          id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          status TEXT NOT NULL DEFAULT 'draft',
          missing_items TEXT NOT NULL DEFAULT '[]',
          packet_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY (report_id) REFERENCES accident_reports(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS action_plans (
          id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          steps_json TEXT NOT NULL DEFAULT '[]',
          timelines_json TEXT NOT NULL DEFAULT '[]',
          FOREIGN KEY (report_id) REFERENCES accident_reports(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
          id TEXT PRIMARY KEY,
          report_id TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          reason TEXT NOT NULL,
          routed_to TEXT NOT NULL,
          summary TEXT NOT NULL,
          FOREIGN KEY (report_id) REFERENCES accident_reports(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS recommended_resources (
          id TEXT PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          state TEXT,
          topic TEXT NOT NULL,
          resources_json TEXT NOT NULL DEFAULT '[]',
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback_events (
          id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL DEFAULT (strftime('%m/%d/%Y', 'now')),
          customer_id INTEGER,
          agent_name TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL DEFAULT '{}',
          FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        );
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_accident_reports_customer ON accident_reports(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_escalations_report ON escalations(report_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_resources_customer ON recommended_resources(customer_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_customer ON feedback_events(customer_id);")