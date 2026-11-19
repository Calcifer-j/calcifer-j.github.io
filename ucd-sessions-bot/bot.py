import os
import requests
from datetime import datetime, timedelta
from config import LINEAR_TEAM_ID, LINEAR_PROJECT_ID, LINEAR_VIEW_URL

LINEAR_API_KEY = os.environ["LINEAR_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

LINEAR_API = "https://api.linear.app/graphql"

# Statuses that the bot can modify (respects user overrides like Done/Canceled)
BOT_MANAGED_STATUSES = ["Backlog", "Todo", "In Progress"]


def linear_query(query: str, variables: dict = None):
    """Execute a GraphQL query against Linear API."""
    response = requests.post(
        LINEAR_API,
        headers={
            "Authorization": LINEAR_API_KEY,
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables or {}},
    )
    if not response.ok:
        print(f"Linear API error: {response.status_code}", flush=True)
        print(f"Response: {response.text}", flush=True)
        response.raise_for_status()
    data = response.json()
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}", flush=True)
    return data


def post_to_slack(message: str):
    """Post a message to Slack via webhook."""
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": message},
    )
    response.raise_for_status()
    print(f"Posted to Slack: {message[:100]}...")


def get_next_monday(weeks_ahead: int = 0) -> str:
    """Get the date of the next Monday (from today, typically Wednesday)."""
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7  # If today is Monday, get next Monday
    next_monday = today + timedelta(days=days_until_monday + (weeks_ahead * 7))
    return next_monday.strftime("%Y-%m-%d")


def format_date_nice(date_str: str) -> str:
    """Format date for display: '2 December'."""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return date.strftime("%-d %B")


def get_future_sessions():
    """Get all future session issues."""
    today = datetime.now().strftime("%Y-%m-%d")
    query = """
    query($teamId: ID!, $projectId: ID!, $today: TimelessDate!) {
      issues(
        filter: {
          team: { id: { eq: $teamId } }
          project: { id: { eq: $projectId } }
          dueDate: { gte: $today }
        }
        orderBy: dueDate
      ) {
        nodes {
          id
          identifier
          title
          url
          dueDate
          assignee {
            name
            displayName
          }
          state {
            name
            type
          }
          labels {
            nodes {
              name
            }
          }
        }
      }
    }
    """
    result = linear_query(query, {
        "teamId": LINEAR_TEAM_ID,
        "projectId": LINEAR_PROJECT_ID,
        "today": today,
    })
    return result.get("data", {}).get("issues", {}).get("nodes", [])


def find_session_by_date(due_date: str):
    """Find a session issue by its due date."""
    query = """
    query($teamId: ID!, $projectId: ID!, $dueDate: TimelessDate!) {
      issues(
        filter: {
          team: { id: { eq: $teamId } }
          project: { id: { eq: $projectId } }
          dueDate: { eq: $dueDate }
        }
      ) {
        nodes {
          id
          identifier
          title
          url
          dueDate
          assignee {
            name
            displayName
          }
          state {
            name
            type
          }
          labels {
            nodes {
              name
            }
          }
        }
      }
    }
    """
    result = linear_query(query, {
        "teamId": LINEAR_TEAM_ID,
        "projectId": LINEAR_PROJECT_ID,
        "dueDate": due_date,
    })
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])
    return issues[0] if issues else None


def create_session(due_date: str, status: str = "Backlog"):
    """Create a new session issue."""
    nice_date = format_date_nice(due_date)
    query = """
    mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          title
          url
        }
      }
    }
    """
    result = linear_query(query, {
        "input": {
            "teamId": LINEAR_TEAM_ID,
            "projectId": LINEAR_PROJECT_ID,
            "title": f"UCD Session: {nice_date} - volunteer needed",
            "dueDate": due_date,
            "stateId": get_status_id(status),
            "description": f"## UCD Playback Session\n\n**Date:** Monday {nice_date}\n\n**Presenter:** _Volunteer needed!_\n\n**Theme:** TBC\n\n**Topic:** TBC\n\n---\n\n**To volunteer:** Assign yourself to this issue, pick a theme label, and update the title with your topic.",
        }
    })
    return result.get("data", {}).get("issueCreate", {}).get("issue")


def get_status_id(status_name: str) -> str:
    """Get the status ID for a given status name."""
    query = """
    query($teamId: ID!) {
      team(id: $teamId) {
        states {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    result = linear_query(query, {"teamId": LINEAR_TEAM_ID})
    states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])
    for state in states:
        if state["name"].lower() == status_name.lower():
            return state["id"]
    return None


def update_issue_status(issue_id: str, status_name: str):
    """Update an issue's status."""
    status_id = get_status_id(status_name)
    if not status_id:
        print(f"  ⚠ Could not find status: {status_name}")
        return
    
    query = """
    mutation($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
      }
    }
    """
    linear_query(query, {"id": issue_id, "input": {"stateId": status_id}})


def ensure_six_future_sessions():
    """Make sure there are 6 future Monday sessions."""
    print("\n📅 Ensuring 6 future sessions exist...")
    
    # Get existing future sessions
    existing = get_future_sessions()
    existing_dates = {s["dueDate"] for s in existing if s.get("state", {}).get("type") != "canceled"}
    
    print(f"  Found {len(existing_dates)} existing future sessions")
    
    # Calculate next 6 Mondays
    needed_mondays = [get_next_monday(i) for i in range(6)]
    
    # Create any missing
    for monday in needed_mondays:
        if monday not in existing_dates:
            nice_date = format_date_nice(monday)
            print(f"  Creating session for {nice_date}...")
            create_session(monday)
    
    print("  ✓ 6 future sessions ensured")


def update_statuses():
    """Update statuses: this Monday = In Progress, next Monday = To Do, others = Backlog."""
    print("\n🔄 Updating statuses...")
    
    this_monday = get_next_monday(0)
    next_monday = get_next_monday(1)
    
    sessions = get_future_sessions()
    
    for session in sessions:
        current_status = session.get("state", {}).get("name", "")
        due_date = session.get("dueDate")
        
        # Skip if user has set a non-bot-managed status (Done, Canceled, etc.)
        if current_status not in BOT_MANAGED_STATUSES:
            print(f"  Skipping {session['identifier']} - user set status: {current_status}")
            continue
        
        # Determine target status
        if due_date == this_monday:
            target = "In Progress"
        elif due_date == next_monday:
            target = "Todo"
        else:
            target = "Backlog"
        
        # Update if different
        if current_status != target:
            print(f"  {session['identifier']}: {current_status} → {target}")
            update_issue_status(session["id"], target)
        else:
            print(f"  {session['identifier']}: already {current_status}")


def announce_this_monday():
    """Post Slack message about this Monday's session."""
    print("\n📢 Announcing this Monday's session...")
    
    this_monday = get_next_monday(0)
    this_monday_nice = format_date_nice(this_monday)
    
    session = find_session_by_date(this_monday)
    
    if not session:
        print("  ⚠ No session found - should have been created earlier")
        return
    
    # Skip if canceled
    if session.get("state", {}).get("type") == "canceled":
        print("  Session is canceled, skipping announcement")
        return
    
    assignee = session.get("assignee")
    
    if assignee:
        presenter = assignee.get("displayName") or assignee.get("name")
        topic = session.get("title", "").replace("UCD Session: ", "").replace(f"{this_monday_nice} - ", "")
        print(f"  ✓ Has presenter: {presenter}")
        post_to_slack(
            f"**Hey everyone!** :sunny: Quick reminder: next Monday's session is {topic} being presented by {presenter}.\n\n"
            f"<{LINEAR_VIEW_URL}|See all upcoming sessions> and add your details to volunteer."
        )
    else:
        print(f"  ✗ No presenter!")
        post_to_slack(
            f"**Hey everyone!** :heart_hands: This Monday's session ({this_monday_nice}) needs a presenter!\n\n"
            f"Please <{session['url']}|volunteer if you have time>. "
            f"You can also <{LINEAR_VIEW_URL}|see all upcoming sessions>."
        )


def run():
    """Main bot logic - runs every Wednesday."""
    print("🤖 UCD Sessions Bot running (Wednesday check)...")
    
    # 1. Ensure 6 future sessions exist
    ensure_six_future_sessions()
    
    # 2. Update statuses (this Monday = In Progress, next = To Do, rest = Backlog)
    update_statuses()
    
    # 3. Post Slack announcement for this Monday
    announce_this_monday()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    run()
