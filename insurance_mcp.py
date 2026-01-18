#imports
from fastmcp import FastMCP
from typing import List, Dict

mcp = FastMCP("AutoInsuranceMCP")

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
    # Your implementation here
    # This could query a database, call an API, etc.
    return {
        "id": id,
        "name": name,
        "age": age,
        "state": state,
        "vehicleName": vehicleName,
        "coverageType": coverageType
    }