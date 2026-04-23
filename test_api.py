import requests

url = "http://127.0.0.1:8000/format-report"

payload = {
    "raw_text": """Arun
Bug:
inte- 1059, 1067
"""
}

response = requests.post(url, json=payload)

# 👇 ADD THIS
print("\nFULL RESPONSE:\n")
print(response.text)

data = response.json()

print("\nPARSED JSON:\n")
print(data)