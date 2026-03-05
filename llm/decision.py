import asyncio
import os
from openai import OpenAI
from tavily import TavilyClient

from db.postgres import fetch_events
from blockchain.transact import validate_event
from dotenv import load_dotenv
load_dotenv()

client = OpenAI()
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# TODO: think about decentralized oracle architecture with several LLMs agents in parallel

SYSTEM_PROMPT = """
You are an objective blockchain oracle.

Your task:
1. Search the web using available tools.
2. Determine the correct answer to the question.
3. Provide the final answer strictly as one of the provided options.
4. Provide one reliable source URL.

Rules:
- Only use publicly verifiable information.
- Do not speculate.
- If uncertain, return: {"answer": "REFUND", "source": "not found"}

Return strictly valid JSON:

{
  "answer": "...",
  "source": "https://..."
}
"""


async def decision_maker():
    events = fetch_events()

    if not events:
        print("No events")
        return

    for event in events:
        try:
            print(f"Processing event {event.id}")

            result = await llm_answer(
                event.question,
                event.answers
            )

            await validate_event(
                event.id,
                result["answer"],
                result["source"]
            )

        except Exception as e:
            print(f"Error processing event {event.id}: {e}")


# TODO: test
async def llm_answer(question, options):

    response = client.responses.create(
        model="gpt-4.1",
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "oracle_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "source": {"type": "string"}
                    },
                    "required": ["answer", "source"]
                }
            }
        },
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""
        Question:
        {question}

        Options:
        {options}
        """
            }
        ]
    )

    result = response.output_parsed

    # --- Sanity checks ---
    if result["answer"] not in options and result["answer"] != "REFUND":
        print.error("AI returned invalid option")

    if result["answer"] != "REFUND" and not result["source"].startswith("http"):
        print.error("Invalid source")

    return result


async def cron_loop():
    while True:
        await decision_maker()
        await asyncio.sleep(300)  # 5 minutes
