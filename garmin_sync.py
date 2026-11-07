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

def fetch_activity_laps(access_token, activity_id):
    """Hämtar detaljerade varv (laps/splits) för en specifik aktivitet från Garmins API."""
    # Garmin Connect API endpoint för laps/splits
    url = f"https://personal.connectapi.garmin.com/activity-service/activity/{activity_id}/splits"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            # Returnerar lap-listan (ofta under lapDTOs eller liknande)
            return data.get("lapDTOs", data.get("splitSummaries", []))
    except Exception:
        return []

def main():
    if not API_KEY:
        print("Fel: GARMIN_API_KEY saknas i miljövariablerna.")
        exit(1)

    print("Autentiserar mot Garmin Personal API...")
    token_url = "https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token"
    token_req = urllib.request.Request(
        token_url,
        data=b"",
        headers={"Authorization": f"ApiKey {API_KEY}"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(token_req) as token_response:
            access_token = token_response.read().decode("utf-8").strip()

        print("Hämtar aktivitetslista...")
        all_activities = []
        start = 0
        limit = 100

        while True:
            activities_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start={start}&limit={limit}"
            act_req = urllib.request.Request(
                activities_url,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            )
            with urllib.request.urlopen(act_req) as act_response:
                batch = json.loads(act_response.read().decode("utf-8"))
                if isinstance(batch, dict):
                    batch = batch.get("activityList", [])
                if not batch:
                    break
                all_activities.extend(batch)
                if len(batch) < limit:
                    break
                start += limit

        # Hämta detaljerade laps per aktivitet och lägg till i objektet
        print("Hämtar kilometer-laps för varje pass...")
        for act in all_activities:
            act_id = act.get("activityId")
            if act_id:
                laps = fetch_activity_laps(access_token, act_id)
                if laps:
                    act["laps"] = json.dumps(laps, ensure_ascii=False)

        raw_combined = {get_activity_id(a): a for a in all_activities if get_activity_id(a)}

        # Läs in befintlig CSV för att behålla historik
        if os.path.exists(FILENAME):
            with open(FILENAME, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    act_id = get_activity_id(row)
                    if act_id and act_id not in raw_combined:
                        restored = {}
                        for k, v in row.items():
                            try:
                                restored[k] = json.loads(v)
                            except Exception:
                                restored[k] = v
                        raw_combined[act_id] = restored

        # Bygg kolumnlistan
        fieldnames = sorted(list(set(k for a in raw_combined.values() for k in a.keys())))

        # Spara till CSV
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

        print(f"Klart! {len(raw_combined)} aktiviteter sparade till {FILENAME}.")

    except Exception as err:
        print(f"Ett fel uppstod: {err}")
        exit(1)

if __name__ == "__main__":
    main()
