from dotenv import load_dotenv
load_dotenv()
import anthropic
import os
from flask import Flask, request, render_template

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/plan", methods=["POST"])
def plan():
    destination = request.form.get("destination", "").strip()
    days = request.form.get("days", "").strip()
    budget = request.form.get("budget", "").strip()
    style = request.form.get("style", "balanced").strip()

    if not destination or not days or not budget:
        return render_template("index.html", error="Please fill in all fields.")

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": f"""You are a practical travel planner.
Create a {days}-day trip to {destination} for someone with a ${budget} total budget and a {style} travel style.

For each day, pick ONE main activity that anchors the day. Then suggest at most ONE other activity that realistically fits given travel time and energy.

For each day include:
- How long the main activity actually takes including queues and transport
- The best time to arrive
- Realistic daily cost breakdown
- One nearby restaurant with price range
- One thing most tourists get wrong about that day"""
            }]
        )

        itinerary = response.content[0].text
        return render_template("index.html",
            itinerary=itinerary,
            destination=destination,
            days=days,
            budget=budget,
            style=style
        )

    except Exception as e:
        return render_template("index.html",
    itinerary=itinerary,
    destination=destination,
    days=days,
    budget=budget,
    style=style
)

if __name__ == "__main__":
    app.run(debug=True)