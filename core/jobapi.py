import requests

def fetch_jobs_from_jooble(keywords, location):
    url = "https://jooble.org/api/db9c9cda-73a7-418d-bc87-3d793d4c2bcf"
    
    headers = {"Content-Type": "application/json"}
    data = {
        "keywords": keywords,
        "location": location
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        try:
            result = response.json()
            jobs = result.get('jobs', [])
            if isinstance(jobs, list):
                return jobs
            else:
                print("Unexpected format inside 'jobs':", type(jobs))
                return []
        except ValueError:
            print("JSON Decode Error:", response.text)
            return []
    else:
        print(f"API Error {response.status_code}: {response.text}")
        return []
