import os
import csv
import urllib.request
import urllib.error
import json

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"

def get_activity_id(act):
    raw_id = act.get("activityId") or act.get("startTimeLocal")
    return str(raw_id) if raw_id is not None else None

def fetch_activity_details(access_token, activity_id):
    """Hämtar detaljerad data inklusive laps för varje enskilt pass."""
    url = f"https://personal.connectapi.garmin.com/activity-service/activity/{activity_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}

def main():
    if not API_KEY:
        print("Fel: GARMIN_API_KEY saknas.")
        exit(1)

    token_url = "https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token"
    token_req = urllib.request.Request(
        token_url,
        data=b"",
        headers={"Authorization": f"ApiKey {API_KEY}"},
        method="POST"
    )

    with urllib.request.urlopen(token_req) as resp:
        access_token = resp.read().decode("utf-8").strip()

    # 1. Hämta grundläggande aktivitetslista
    all_activities = []
    start, limit = 0, 100

    while True:
        search_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start={start}&limit={limit}"
        req = urllib.request.Request(search_url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req) as r:
            batch = json.loads(r.read().decode("utf-8"))
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < limit:
                break
            start += limit

    # 2. Hämta detaljer (laps/splits) för varje pass
    print("Hämtar detaljerade varv (laps) per aktivitet...")
    for act in all_activities:
        act_id = act.get("activityId")
        if act_id:
            details = fetch_activity_details(access_token, act_id)
            if details:
                act.update(details)
                # Garmin sparar ofta laps i 'lapDTOs' eller 'splitSummaries'
                if "lapDTOs" in details:
                    act["laps"] = json.dumps(details["lapDTOs"], ensure_ascii=False)

    # 3. Spara till CSV
    raw_combined = {get_activity_id(a): a for a in all_activities if get_activity_id(a)}
    
    fieldnames = sorted(list(set(k for a in raw_combined.values() for k in a.keys())))

    with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fieldnames)
        for act in sorted(raw_combined.values(), key=lambda x: str(x.get("startTimeLocal", "")), reverse=True):
            row = []
            for field in fieldnames:
                val = act.get(field, "")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row.append(val)
            writer.writerow(row)

    print(f"Klart! {len(raw_combined)} aktiviteter sparade med komplett data.")

if __name__ == "__main__":
    main()
