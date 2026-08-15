import requests

# Legacy script from hassvm (2025-06-22).
# Plain requests no longer work reliably because hattrick.org is behind Cloudflare.
# Use hattrick_login.py instead.


def login(username, password):
    session = requests.Session()
    response = session.post(
        "https://www.hattrick.org/en-us/Login",
        data={
            "ctl00$CPContent$ucLogin$txtUserName": username,
            "ctl00$CPContent$ucLogin$txtPassword": password,
        },
    )
    if "Authentication failed" not in response.text:
        return session
    return None


def get_finances_page(session, team_id):
    response = session.get(f"https://www.hattrick.org/Club/Finances/?teamId={team_id}")
    if response.status_code == 200:
        return response.content
    return b""


def main():
    username = "YOUR_USERNAME"
    password = "YOUR_PASSWORD"
    team_id = "YOUR_TEAM_ID"

    session = login(username, password)
    if session:
        print(get_finances_page(session, team_id))
    else:
        print("Failed to log in to Hattrick.")


if __name__ == "__main__":
    main()
