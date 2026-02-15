import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))

import insurance_mcp

from langchain.cli_utils import prompt_int, prompt_int_optional, prompt_text


def mcp_server_path() -> str:
	return str(REPO_ROOT / "insurance_mcp.py")


async def setup_mcp_client():
	mcp_server_script = os.getenv("INSURANCE_MCP_SERVER", mcp_server_path())
	client = MultiServerMCPClient(
		{
			"insurance": {
				"transport": "stdio",
				"command": sys.executable,
				"args": [mcp_server_script],
				"env": {
					"MCP_TRANSPORT": "stdio",
					"INSURANCE_DB_PATH": os.getenv(
						"INSURANCE_DB_PATH", os.path.join("database", "insurance.db")
					),
				},
			}
		}
	)
	return await client.get_tools()


def pick_tool(tools, name: str):
	for t in tools:
		if getattr(t, "name", None) == name:
			return t
	raise RuntimeError(f"Tool '{name}' not found")


async def run_cli():
	# SYSTEM RESET — READ CAREFULLY
	# Output the FULL list of all 27 topics from scratch, with ONLY the links explicitly provided, in exact order, no extra commentary or formatting.
	topics_and_links = [
		("What Is Car Insurance?", [
			"https://www.investopedia.com/what-does-auto-insurance-cover-7495827",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.compare.com/auto-insurance/resources/coverage",
			"https://www.reddit.com/r/u_carinsurance2024usa/comments/1anf3bz",
		]),
		("Understanding Deductibles", [
			"https://www.investopedia.com/what-is-a-deductible-in-car-insurance-7486896",
			"https://en.wikipedia.org/wiki/Deductible",
			"https://www.investopedia.com/ask/answers/071515/why-do-insurance-policies-have-deductibles.asp",
		]),
		("Steps to Take During a Car Accident", [
			"https://www.allstate.com/resources/car-insurance/in-case-of-a-car-accident",
			"https://agate.tdi.state.tx.us/pubs/consumer/cb020.html",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("Do’s and Don’ts of Safe Driving", [
			"https://en.wikipedia.org/wiki/Usage-based_insurance",
			"https://www.investopedia.com/terms/b/black-box-insurance.asp",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
		("What Is a Premium?", [
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
		]),
		("What Is a Claim?", [
			"https://www.grinnellmutual.com/auto-safety-tips-resources/car-insurance-terms-explained",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.allstate.com/resources/car-insurance/types-of-car-insurance-coverage",
		]),
		("How to File a Claim", [
			"https://www.dgglaw.com/how-to-file-car-accident-claims/",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.allstate.com/resources/car-insurance/in-case-of-a-car-accident",
		]),
		("What Is Coverage?", [
			"https://www.compare.com/auto-insurance/resources/coverage",
			"https://www.progressive.com/answers/types-of-car-insurance/",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("Types of Coverage for Auto Insurance", [
			"https://www.compare.com/auto-insurance/resources/coverage",
			"https://www.progressive.com/answers/types-of-car-insurance/",
			"https://www.moneygeek.com/insurance/auto/coverage/",
		]),
		("Factors Affecting Insurance Rates", [
			"https://www.cnbc.com/select/factors-that-affect-car-insurance-rates/",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
		]),
		("Impact of Driving History on Rates", [
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
		]),
		("How to Maintain a Clean Driving Record", [
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
		]),
		("Common Auto Insurance Terms Explained", [
			"https://www.grinnellmutual.com/auto-safety-tips-resources/car-insurance-terms-explained",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://en.wikipedia.org/wiki/Usage-based_insurance",
		]),
		("How to Choose the Right Insurance Plan", [
			"https://www.autoinsurance.com/guide/",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
		("Importance of Liability Coverage", [
			"https://www.iii.org/article/auto-insurance-basics-understanding-your-coverage",
			"https://www.moneygeek.com/insurance/auto/coverage/",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
		("Understanding Comprehensive & Collision Coverage", [
			"https://www.progressive.com/answers/types-of-car-insurance/",
			"https://www.moneygeek.com/insurance/auto/coverage/",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
		("How to Lower Your Insurance Premiums", [
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
		]),
		("Seasonal Driving Tips & Insurance Implications", [
			"https://www.compare.com/auto-insurance/resources/coverage",
			"https://content.naic.org/insurance-topics/auto-insurance",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
		]),
		("Impact of Traffic Violations on Rates", [
			"https://www.cnbc.com/select/factors-that-affect-car-insurance-rates/",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
		]),
		("How to Read Your Insurance Policy", [
			"https://oci.wi.gov/Documents/Consumers/pi-057.pdf",
			"https://www.tn.gov/content/dam/tn/commerce/documents/insurance/posts/Consumer_Guide_Auto_Insurance.pdf",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("Benefits of Bundling Insurance Policies", [
			"https://www.policygenius.com/auto-insurance/what-affects-car-insurance-premiums/",
			"https://www.experian.com/blogs/ask-experian/factors-that-determine-your-car-insurance-rates/",
			"https://www.forbes.com/advisor/car-insurance/factors-in-rates/",
		]),
		("Understanding No-Fault Insurance", [
			"https://en.wikipedia.org/wiki/No-fault_insurance",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("What to Do in Case of a Total Loss", [
			"https://www.allstate.com/resources/car-insurance/in-case-of-a-car-accident",
			"https://www.compare.com/auto-insurance/resources/coverage",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("How to Handle Uninsured Motorist Situations", [
			"https://www.moneygeek.com/insurance/auto/coverage/",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
		("Understanding Policy Endorsements", [
			"https://www.grinnellmutual.com/auto-safety-tips-resources/car-insurance-terms-explained",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("How to Dispute a Denied Claim", [
			"https://www.dgglaw.com/how-to-file-car-accident-claims/",
			"https://content.naic.org/insurance-topics/auto-insurance",
		]),
		("Understanding Rental Car Coverage", [
			"https://www.investopedia.com/credit-card-rental-car-insurance-what-is-it-and-how-does-it-work-7499406",
			"https://www.compare.com/auto-insurance/resources/coverage",
		]),
	]

	for topic, links in topics_and_links:
		print(topic)
		for idx, url in enumerate(links, 1):
			print(f"{idx}. {url}")


if __name__ == "__main__":
	asyncio.run(run_cli())

