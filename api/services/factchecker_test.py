import os, requests

API_KEY = os.getenv("GOOGLE_FACTCHECK_API_KEY")
url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
params = {"query": "5G causes COVID-19", "languageCode": "en", "pageSize": 3, "key": API_KEY}
r = requests.get(url, params=params, timeout=10)
print(r.json())
