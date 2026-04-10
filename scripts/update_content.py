import requests
import json
import anthropic
import os
from datetime import date

# ── CONFIGURATION ──────────────────────────────────────────
# The three pages we scrape from the Youth Riders website.
# If they add new pages later (e.g. /shop/) you'd add them here.

PAGES = {
    "home":    "https://youth-riders.org.uk/",
    "events":  "https://youth-riders.org.uk/events-calendar/",
    "sponsors":"https://youth-riders.org.uk/sponsors/"
}

# ── STEP 1: FETCH THE WEB PAGES ────────────────────────────
def fetch_page(url):
    """
    Downloads a web page and returns its raw text.
    We cap at 8,000 characters to keep Claude API costs low —
    the important content (events, news titles) is always 
    near the top of the page.
    """
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "YouthRidersBot/1.0"}
        )
        response.raise_for_status()
        return response.text[:8000]
    except Exception as e:
        print(f"Warning: Could not fetch {url}: {e}")
        return f"[Page unavailable: {url}]"

# ── STEP 2: SEND TO CLAUDE FOR EXTRACTION ─────────────────
def extract_content(pages_text):
    """
    Sends the raw page text to Claude and asks it to extract
    structured JSON. Claude handles all the messy HTML parsing,
    date interpretation, and categorisation — we just ask for
    clean JSON back.
    """
    # Get the API key from the environment variable set by GitHub Actions
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    today = date.today().isoformat()
    
    prompt = f"""You are a data extraction assistant for the Youth Riders charity website.
    
Extract content from these web pages and return structured JSON.

TODAY'S DATE: {today}
Only include events that are in the FUTURE relative to today's date.

HOME PAGE (contains latest news posts):
{pages_text['home']}

EVENTS CALENDAR PAGE:
{pages_text['events']}

SPONSORS PAGE:
{pages_text['sponsors']}

Return ONLY a valid JSON object with this exact structure. 
No markdown code blocks. No explanation. Just the raw JSON:

{{
  "lastUpdated": "{today}",
  "events": [
    {{
      "day": "DD",
      "month": "MMM",
      "name": "Event name",
      "location": "Venue, Town",
      "description": "1-2 sentence description",
      "entry": "Entry info e.g. Free entry or £5",
      "tags": ["choose from: skate, bmx, scoot, free, comp"]
    }}
  ],
  "news": [
    {{
      "category": "Category label",
      "title": "Post title",
      "date": "Month YYYY",
      "body": "2-3 sentence summary",
      "accentColor": "var(--orange)"
    }}
  ],
  "sponsors": [
    {{
      "name": "Sponsor name",
      "description": "One line description of their support",
      "tier": "gold",
      "url": "https://their-website.com"
    }}
  ]
}}

Rules:
- Events: only include future events. If no date visible, skip it.
- Events: month should be 3-letter abbreviation e.g. Jun, Jul, Apr
- Events: tags — skate/bmx/scoot for discipline, free if no entry cost, comp if competition
- News: take the 3 most recent posts from the home page
- News accentColor: Sponsorship=var(--orange), Park Update or Changes=var(--blue), 
  Breaking News=var(--lime), anything else=var(--grey)
- Sponsors: if no named sponsors found, return empty array []
- Tier: use gold for headline sponsors, silver for supporters, partner for others
- Return ONLY the JSON object, nothing else whatsoever"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text.strip()

# ── STEP 3: VALIDATE AND SAVE ──────────────────────────────
def save_data(raw_json):
    """
    Parses the JSON Claude returned to validate it's correct,
    then writes it to data.json. If Claude returned invalid JSON
    for any reason, this will raise an error and the GitHub Action
    will fail visibly rather than silently corrupting data.json.
    """
    # This will raise json.JSONDecodeError if Claude returned 
    # anything other than valid JSON
    data = json.loads(raw_json)
    
    # Basic sanity checks
    assert "events" in data, "Missing events array"
    assert "news" in data, "Missing news array"
    assert "sponsors" in data, "Missing sponsors array"
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return data

# ── MAIN ────────────────────────────────────────────────────
def main():
    print(f"Starting content update — {date.today()}")
    
    print("Fetching pages from youth-riders.org.uk...")
    pages_text = {}
    for key, url in PAGES.items():
        print(f"  Fetching {url}...")
        pages_text[key] = fetch_page(url)
    
    print("Sending to Claude API for extraction...")
    raw_json = extract_content(pages_text)
    
    print("Validating and saving data.json...")
    data = save_data(raw_json)
    
    print(f"\nSuccess:")
    print(f"  Events:   {len(data['events'])}")
    print(f"  News:     {len(data['news'])}")
    print(f"  Sponsors: {len(data['sponsors'])}")
    print(f"  Updated:  {data['lastUpdated']}")

if __name__ == "__main__":
    main()
