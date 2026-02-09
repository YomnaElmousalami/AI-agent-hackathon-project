# Insurance AI-Agent

## Phase 1:

**Problem Statement:** Many first-time drivers in the USA (often 16-17 years old) struggle to understand auto insurance. Relevant information is scattered across different websites, PDFs, and YouTube Videos, making it time-consuming and confusing to learn concepts like coverage, claims, and deductibles. When an accident occurs, these drivers often spend excessive time contacting customer service or searching for resources to solve their case. This inefficiency not only frustrates users but also burdens insurance companies. By leveraging ai agents, it is estimated that more than 30% of Tier-1 customer support calls could be reduced during an accident, therefore,
providing faster guidance for new drivers while improving operational efficiency for insurers.

**Example Workflow:**
Learning & Education Mode:
- User Onboarding Agent collects basic context such as id, name, age, state, vehicle name (like Honda Accord), and coverage type to personalize learning for each user
- Curriculum Planner Agent breaks insurance concepts into easily digestbile driver modules so they can be used for the teacher agent later. Ex: What is insurance, what deductibles mean, what happens during an accident, what to do vs. what not to do? This replaces repetitive "what is X?" calls to insurance workers.
- Teacher Agent explains coverage, deductibles, claims, and other auto insurance terms in plain, age-appropriate language. This will be done with definitions, examples relevant to first time drivers, and metaphors. It can also context switch such as: "Explain xyz like im 16," or "I need a quick refresher on deductibles"
- Knowledge Validation Agent uses short scenarios to confirm understanding and correct knowledge gaps (like a multiple choice and true false quiz type of way)
- Resource Recommendation Agent gathers trusted, US, state-specific resource content without overwhelming the user. This will be done through short videos and summaries of documents rather than dumping links onto the user. 

Accident Mode (Real-Time Assistance):
- Accident Reporting Agent provides immediate safety guidance by collecting accident details and evidence of said accident step-by-step. Ex: is anyone injured, if so how many?, is the veihcle still drivable or is it completely damaged?, Where is your location?, Upload photos/videos.
- Accident Severity Assesment Agent categorizes the accident (rear-end, etc.) and determines urgency or escalation needs (like if there is an emergency).
- Policy Interpretation Agent translates the user’s policy into clear coverage (what can and can't be covered) and cost expectations (such as for deductibles that need to be paid)
- Claims Preparation Agent verifies required information and prepares claim-ready documents.
- Action Plan Agent Displays and explains next steps, timelines, and possible
outcomes
- Escalation & Routing Agent summarizes the case and routes to human support only when necessary (Hospital phone numbers, etc.).

Continuous Improvement:
- Continuous Improvement & Feedback Agent analyzes where users get stuck and previous escalation patterns to improve future interactions. 

**Technical Arcitecture Diagram:**

**Expected Impact:**
- Reduce more than 30% of Tier-1 customer support calls
- Improve customer satisfaction by at least 10%
- Have an average response time of 3 seconds or less
- Explain complicated concepts more simply for the average teen mind


## Phase 2:

### Postman MCP testing (recommended)

Postman expects an HTTP MCP endpoint (SSE-based) at:

- `http://localhost:8000/mcp`

Start the HTTP MCP server using:

```powershell
.\dev_mcp_postman.ps1
```

This script runs the Postman-friendly server runner (`run_mcp_postman.py`) using **Python 3.11** for stability.

#### Windows note (Python 3.14)

On some Windows + Python 3.14 setups, the MCP HTTP server may start and then immediately exit (which makes Postman show ECONNREFUSED / SSE fetch failed). If that happens, run the server using Python 3.11 via the helper script:

```powershell
.\dev_mcp_postman.ps1
```

If you want to try running the basic HTTP runner directly (may be unstable on Python 3.14):

```powershell
python .\run_mcp_http.py
```

Also, if Postman tries IPv6 first (`::1`), make sure `localhost` resolves to IPv4 (`127.0.0.1`) on your machine.

#### Step-by-step: run MCP in Postman

1) **Start the MCP server (Windows / Postman-friendly)**

Open PowerShell at the repo root and run:

```powershell
.\dev_mcp_postman.ps1
```

This starts the MCP server using **Python 3.11** (more stable than Python 3.14 for MCP HTTP + SSE) and serves MCP at:

- `http://localhost:8000/mcp`

Keep this terminal running.

2) **Connect Postman to your MCP server**

- In Postman: **New** → choose **MCP**
- Transport: **HTTP**
- URL: **`http://localhost:8000/mcp`**

Postman should auto-discover the tools from your server.

3) **Execute a tool**

Once connected, Postman will show a list of tools from `insurance_mcp.py`. Pick any tool, fill in the parameters form, and click **Send**.

#### Troubleshooting

- **SSE / ECONNREFUSED / ::1 (IPv6 localhost)**
	- Postman sometimes tries IPv6 first (`::1`). If that fails, force IPv4 localhost:
		- Edit (as Admin): `C:\Windows\System32\drivers\etc\hosts`
		- Ensure these lines exist:
			- `127.0.0.1 localhost`
			- `# ::1 localhost`

- **Port already in use**
	- If port 8000 is busy, set before running the script:

```powershell
$env:MCP_PORT = "8000"   # change as needed
.\dev_mcp_postman.ps1
```

## Phase 3:
Use a hugging face model, so far using llama3.2 but may change later: https://huggingface.co/models

## Phase 4:
Learning & Education Mode:

- To run the user onboarding agent:
"python -m langchain.user_onboarding_agent"

- To run the curriculum planner agent:
"python .\langchain\curriculum_planner_agent.py"

- To run the teacher agent:
"python -m langchain.teacher_agent"

- To run the knowledge validation agent:
"python .\langchain\knowledge_validation_agent.py"

- To run the resource recommendation agent:
"python .\langchain\resource_recommendation_agent.py"

Accident Mode (Real-Time Assistance):

- To run the accident reporting agent:
"python .\langchain\accident_reporting_agent.py"

- To run the accident severity assessment agent:
"python .\langchain\accident_severity_assesment_agent.py"

- To run the policy interpretation agent:
"python .\langchain\policy_interpretation_agent.py"

- To run the claims preparation agent:
"python .\langchain\claims_preparation_agent.py"

- To run the action plan agent:
"python .\\langchain\\action_plan_agent.py"

- To run the action plan agent:
"python .\langchain\action_plan_agent.py"

### Optional: run agents in full "agentic" mode (LLM + MCP tools)

Some agents default to a deterministic **tool-first CLI** for reliability and stable tests, but can be switched into a LangGraph **ReAct** loop (LLM decides when/how to call MCP tools) via env vars.

- Policy Interpretation Agent:
	- tool mode (default): `python .\langchain\policy_interpretation_agent.py`
	- agent mode: set `POLICY_AGENT_MODE=agent`

- Claims Preparation Agent:
	- tool mode (default): `python .\langchain\claims_preparation_agent.py`
	- agent mode: set `CLAIMS_AGENT_MODE=agent`

- Action Plan Agent:
	- tool mode (default): `python .\langchain\action_plan_agent.py`
	- agent mode: set `ACTION_PLAN_AGENT_MODE=agent`

- Escalation & Routing Agent:
	- tool mode (default): `python .\langchain\escalation_and_routing_agent.py`
	- agent mode: set `ESCALATION_AGENT_MODE=agent`
- To run the escalation & routing agent:
"python .\langchain\escalation_and_routing_agent.py"

Continuous Improvement:

- To run the continuous improvement & feedback agent:
"python .\langchain\continuous_improvement_and_feedback_agent.py"


To run frontend:

so database can work:
python -m uvicorn api_server:app --host 127.0.0.1 --port 8801

so frontend can work:
npm run dev

## YouTube videos (Option B: real, available videos via YouTube Data API)

The Teacher page can fetch real embeddable YouTube videos per module topic.

1) Create a Google Cloud project
2) Enable **YouTube Data API v3**
3) Create an API key
4) Set it in your backend environment:

```powershell
$env:YOUTUBE_API_KEY = "YOUR_KEY_HERE"
python -m uvicorn api_server:app --host 127.0.0.1 --port 8801
```

If `YOUTUBE_API_KEY` isn't set, `/api/teacher/youtube` will return a 501 with instructions.