# Insurance AI-Agent

## Phase 1:

**Problem Statement:** Many first-time drivers in the USA (often 16-17 years old) struggle to understand auto insurance. Relevant information is scattered across different websites, PDFs, and YouTube Videos, making it time-consuming and confusing to learn concepts like coverage, claims, and deductibles. When an accident occurs, these drivers often spend excessive time contacting customer service or searching for resources to solve their case. This inefficiency not only frustrates users but also burdens insurance companies. By leveraging ai agents, it is estimated that more than 30% of Tier-1 customer support calls could be reduced during an accident, therefore,
providing faster guidance for new drivers while improving operational efficiency for insurers.

**Example Workflow:**
Learning & Education Mode:
- User Onboarding Agent collects basic context such as id, name, age, state, vehicle name (like Honda Accord), and coverage type to personalize learning for each user
- Curriculum Planner Agent breaks insurance concepts into easily digestbile driver modules so they can be used for the teacher agent later. Ex: What is insurance, what deductibles mean, what happens during an accident, what to do vs. what not to do? This replaces repetitive "what is X?" calls to insurance workers.
- Teacher Agent explains coverage, deductibles, claims, and other auto insurance terms in plain, age-appropriate language. This will be done with definitions, examples relevant to first time drivers, and metaphors. It can also context switch such as: "Explain xyz like im 16," or "I need a quick refresher on deductibles"
- Knowledge Validation Agent uses short scenarios to confirm understanding and correct knowledge gaps (in a quizlet style way)
- Resource Recommendation Agent gathers trusted, US, state-specific resource content without overwhelming the user. This will be done through short videos and summaries of documents rather than dumping links onto the user. 

Accident Mode (Real-Time Assistance):
- Accident Reporting Agent provides immediate safety guidance by collecting accident details and evidence of said accident step-by-step. Ex: is anyone injured, if so how many?, is the veihcle still drivable or is it completely damaged?, Where is your location?, Upload photos/videos.
- Accident Severity Assesment Agent categorizes the accident (rear-end, etc.) and determines urgency or escalation needs (like if there is an emergency).
- Policy Interpretation Agent translates the user’s policy into clear coverage (what can and can't be covered) and cost expectations (such as for deductibles that need to be paid)
- Claims Preparation Agent verifies required information and prepares claim-ready documents.
- Action Plan Agent explains next steps, timelines, and possible
outcomes
- Escalation & Routing Agent summarizes the case and routes to human support only when necessary (Hospital phone numbers, etc.).

**Continuous Improvement:**
- Continuous Improvement & Feedback Agent analyzes where users get stuck and previous escalation patterns to improve future interactions. 

**Technical Arcitecture Diagram:**

**Expected Impact:**
- Reduce more than 30% of Tier-1 customer support calls
- Improve customer satisfaction by at least 10%
- Have an average response time of 3 seconds or less
- Explain complicated concepts more simply for the average teen mind


## Phase 2:
To run the mcp: find "insurance_mcp.py" and type "python .\insurance_mcp.py" in command line and test on postman like it says on the buildathon instructions. 

## Phase 3:
Use a hugging face model, so far using llama3.2 but may change later: https://huggingface.co/models

## Phase 4:
To run the user obnoarding agent:
"python -m langchain.user_onboarding_agent"