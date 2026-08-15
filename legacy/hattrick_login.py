import requests
from bs4 import BeautifulSoup
import http.cookiejar

# Legacy script from hassvm (2023-03-30).
# Plain requests no longer work reliably because hattrick.org is behind Cloudflare.
# Use hattrick_login.py instead.

session = requests.Session()
session.cookies = http.cookiejar.CookieJar()

login_url = "https://www.hattrick.org/en-us/"
response = session.get(login_url)
login_form = BeautifulSoup(response.content, "html.parser").find("form")

form_data = {
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
}

login_endpoint = login_form["action"]
response = session.post(login_endpoint, data=form_data)

if "Set-Cookie" in response.headers:
    print("Login successful!")
else:
    print("Login failed.")
