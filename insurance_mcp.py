#imports
from fastmcp import FastMCP
from typing import List, Dict
from datetime import datetime, timezone
import sqlite3

from database.insurance_db import init_db
import os

# Default DB file now lives under ./database/. You can override with INSURANCE_DB_PATH.
db_path = os.getenv("INSURANCE_DB_PATH", os.path.join("database", "insurance.db"))
mcp = FastMCP("AutoInsuranceMCP")
init_db(db_path)

#Code here is for Learning & Education Mode:

#for user onboarding agent
@mcp.tool()
def get_customer_info(id: int, name: str, age: int, state: str, vehicleName: str, coverageType: str) -> Dict:
    """
    Retrieves customer information by ID, age, state, vehicle name, and coverage type.
    
    Args:
        id: The unique customer identifier,
        name: The name of the customer,
        age: The age of the customer,
        state: The state where the customer resides,
        vehicleName: The name of the customer's vehicle,
        coverageType: The type of insurance coverage the customer has.
    
    Returns:
        Dictionary containing customer details
    """

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        INSERT INTO customers (id, name, age, state, vehicle_name, coverage_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
        name=excluded.name,
        age=excluded.age,
        state=excluded.state,
        vehicle_name=excluded.vehicle_name,
        coverage_type=excluded.coverage_type,
        updated_at=excluded.updated_at;
        """, (id, name, age, state, vehicleName, coverageType, now, now))
        
    return {
        "id": id,
        "name": name,
        "age": age,
        "state": state,
        "vehicleName": vehicleName,
        "coverageType": coverageType,
        "updatedAt": now
    }