


import anthropic

import os
from dotenv import load_dotenv
load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

destination = input("Where do you want to go? ")
days = input("How many days? ")
budget = input("What is your budget in USD? ")

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=4000,
    messages=[{
        "role": "user",
        "content": f"""You are an expert travel planner.
Create a {days}-day itinerary for {destination} with a ${budget} budget.
For each day include: morning/afternoon/evening activities,
estimated cost, one restaurant with price range, one local tip."""
    }]
)

print(response.content[0].text)


