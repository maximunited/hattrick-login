import requests
from bs4 import BeautifulSoup

# Legacy script from hassvm (2023-03-30).
# Plain requests no longer work reliably because hattrick.org is behind Cloudflare.
# Use hattrick_login.py instead.

login_url = "https://www.hattrick.org/en-us/Login"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.hattrick.org/",
}

data = {
    "ctl00$CPContent$ucLogin$txtUserName": "YOUR_USERNAME",
    "ctl00$CPContent$ucLogin$txtPassword": "YOUR_PASSWORD",
}

session = requests.Session()
response = session.post(login_url, headers=headers, data=data)

if "Authentication failed" in response.text:
    print("Login failed")
else:
    print("Login successful")

dashboard_url = "https://www.hattrick.org/en-us/MyHattrick/"
response = session.get(dashboard_url)
print(response.text)
