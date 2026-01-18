#imports
from fastmcp import FastMCP
from typing import List, Dict
from datetime import datetime, timezone
import sqlite3

from database.insurance_db import init_db
import os

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
    
    now = datetime.now(timezone.utc).strftime("%m/%d/%Y")

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


# For Curriculum Planner Agent
@mcp.tool()
def plan_curriculum(customer_id: int) -> List[Dict]:
    """
    Plans a curriculum based on user age.
    
    Args:
        customer_id: The customer's ID 

    Returns:
        List of curriculum items tailored to the users age 
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, name, age, state, vehicle_name, coverage_type FROM customers WHERE id = ?;",
            (customer_id,),
        ).fetchone()

    #may remove later
    if row is None:
        raise ValueError(
            f"Customer {customer_id} not found. Call get_customer_info first to store the profile."
        )

    user_age = int(row["age"])

    curriculum = [
        "What is Insurance?",
        "Understanding Deductibles",
        "Steps to Take During a car accident",
        "Do's and Don'ts of Safe Driving",
        "What is a premium?",
        "What is a claim?",
        "How to file a claim?",
        "What is coverage?",
        "Types of coverage for auto insurance",
        "Factors affecting insurance rates",
        "Common auto insurance terms explained",
        "How to choose the right insurance plan",
        "Importance of liability coverage",
        "Understanding comprehensive and collision coverage",
        "How to lower your insurance premiums",
        "Seasonal driving tips and insurance implications",
        "Impact of traffic violations on insurance rates",
        "How to read your insurance policy",
        "Benefits of bundling insurance policies",
        "Understanding no-fault insurance",
        "What to do in case of a total loss",
        "How to handle uninsured motorist situations",
        "The importance of regular vehicle maintenance for insurance purposes",
        "How to update your insurance policy",
        "Understanding policy endorsements",
        "The claims process: Step-by-step guide",
        "How to dispute a denied claim",
        "The role of an insurance adjuster",
        "Understanding rental car coverage",
        "How to switch insurance providers",
        "The impact of life changes on your insurance needs",
        "Understanding roadside assistance coverage",
        "The importance of accurate vehicle information",
        "How to avoid insurance fraud",
        "Understanding gap insurance",
        "The role of telematics in auto insurance",
        "Understanding the difference between actual cash value and replacement cost",
        "How to handle multiple vehicles on one policy",
        "The impact of driving history on insurance rates",
        "Understanding the grace period for premium payments",
        "How to get discounts on auto insurance",
        "The importance of reviewing your insurance policy annually",
        "Understanding the difference between state minimums and recommended coverage",
        "How to handle insurance after a move",
        "The role of family members in an insurance policy",
        "Understanding the impact of vehicle modifications on insurance",
        "How to choose a deductible amount",
        "The importance of documenting your vehicle's condition",
        "Understanding the difference between personal and commercial auto insurance",
    ]

    if user_age < 18:
        curriculum.insert(10, "Tips for first-time drivers")
        curriculum.insert(11, "How insurance works for young drivers")
        curriculum.insert(12, "Understanding the impact of driving history on insurance rates")
        curriculum.insert(13, "The importance of safe driving courses")
        curriculum.insert(14, "How to maintain a clean driving record")
        curriculum.insert(15, "Understanding insurance requirements for student drivers")
    else:
        curriculum.insert(10, "The role of credit scores in insurance")
        
    curriculum_plan = [
        {
            "module": topic,
            "description": f"A comprehensive overview of {topic.lower()}.",
            "customerAge": user_age,
        }
        for topic in curriculum
    ]
    return curriculum_plan

#for teacher agent
@mcp.tool()
def explain_concept(concept: str, customer_age: int) -> str:
    """
    Explains insurance concepts in plain language tailored to the customer's age.
    
    Args:
        concept: The insurance concept to explain,
        customer_age: The age of the customer.
    Returns:
        A simplified explanation of the insurance concept.
    """
    # Placeholder implementation
    return f"This is a simplified explanation of '{concept}' tailored for a {customer_age}-year-old."


#to run the mcp
if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "http").strip().lower()
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        stateless = os.getenv("MCP_STATELESS_HTTP", "true").strip().lower() in {"1", "true", "yes", "on"}
        mcp.run(
            transport="http",
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("MCP_PORT", "8000")),
            stateless_http=stateless,
        )