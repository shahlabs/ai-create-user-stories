import os
import re
import base64
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (API key)
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")  # e.g., "slalom.atlassian.net"
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")  # e.g., "PROJ"
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_USER_EMAIL = os.getenv("JIRA_USER_EMAIL")
JIRA_COOKIE = os.getenv("JIRA_COOKIE")

# Step 1: Analyze the PNG with OpenAI Vision API
def analyze_figma_png(image_path):
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this UI design in detail, including buttons, forms, screens, and user flows."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ],
            }
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content

# Step 2: Generate User Stories with GPT-4o
def generate_user_stories(design_description):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """Create Jira user stories in this exact format:
                
                Title: [User Story Title]
                Description: As a [role], I want [action] so that [benefit].
                Acceptance Criteria:
                - [Criterion 1]
                - [Criterion 2]
                Priority: High/Medium/Low
                ---"""
            },
            {
                "role": "user",
                "content": f"Design Context: {design_description}"
            }
        ],
        max_tokens=1000,
    )
    return response.choices[0].message.content

# Step 3: Parse stories
def parse_stories(gpt_output):
    """Parse GPT-4o output into structured data"""
    stories = []
    pattern = r"Title: (.*?)\nDescription: (.*?)\nAcceptance Criteria:\n(.*?)\nPriority: (.*?)\n---"
    
    matches = re.findall(pattern, gpt_output, re.DOTALL)
    for match in matches:
        story = {
            "title": match[0].strip(),
            "description": match[1].strip(),
            "acceptance_criteria": [c.strip() for c in match[2].split("- ") if c.strip()],
            "priority": match[3].strip()
        }
        stories.append(story)
    return stories

# Step 4: Create Jira tickets
def create_jira_ticket(story):
    """Create Jira ticket via API"""
    url = f"https://{JIRA_DOMAIN}/rest/api/3/issue"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Cookie": JIRA_COOKIE
        # "Authorization": f"Basic {base64.b64encode(f'{JIRA_USER_EMAIL}:{JIRA_API_TOKEN}'.encode()).decode()}"
    }
    
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": story["title"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": story["description"]}]
                    },
                    {
                        "type": "bulletList",
                        "content": [
                            {
                                "type": "listItem",
                                "content": [{"type": "paragraph", "content": [{"type": "text", "text": crit}]}]
                            } for crit in story["acceptance_criteria"]
                        ]
                    }
                ]
            },
            "issuetype": {"name": "Story"},
            # "priority": {"name": story["priority"]}
        }
    }
    
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code, response.json()

if __name__ == "__main__":
    # Configuration
    image_path = "figma_design_1.png"
    
    try:
        # Step 1: Analyze design
        print("Analyzing Figma design...")
        design_description = analyze_figma_png(image_path)
        
        # Step 2: Generate user stories
        print("Generating user stories...")
        raw_stories = generate_user_stories(design_description)
        
        # Step 3: Parse stories
        print("Parsing stories...")
        stories = parse_stories(raw_stories)
        
        # Step 4: Create Jira tickets
        print("Creating Jira tickets...")
        for idx, story in enumerate(stories, 1):
            status_code, response = create_jira_ticket(story)
            if status_code == 201:
                print(f"Created ticket #{idx}: {story['title']} (ID: {response.get('id', '')})")
            else:
                print(f"Failed to create ticket #{idx}: {response}")
                
    except Exception as e:
        print(f"Error: {str(e)}")