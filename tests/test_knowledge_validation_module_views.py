import sqlite3

import insurance_mcp
from database.insurance_db import init_db


def test_record_knowledge_validation_module_view_is_append_only(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    customer_id = 99
    insurance_mcp.create_customer_impl(
        customer_id=customer_id,
        name="KV User",
        age=16,
        state="CA",
        vehicle_name="Honda",
        coverage_type="Liability",
        database_path=db_path,
    )

    v1 = insurance_mcp.record_knowledge_validation_module_view_impl(
        customer_id=customer_id, module_order=1, database_path=db_path
    )
    v2 = insurance_mcp.record_knowledge_validation_module_view_impl(
        customer_id=customer_id, module_order=1, database_path=db_path
    )

    assert v1["viewId"] != v2["viewId"]
    assert v1["moduleOrder"] == 1

    rows = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT module_order FROM knowledge_validation_module_views WHERE customer_id=? ORDER BY created_at",
            (customer_id,),
        ).fetchall()

    assert len(rows) == 2
    assert [r[0] for r in rows] == [1, 1]
