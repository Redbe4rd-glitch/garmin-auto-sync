import os
import csv
import urllib.request
import urllib.error
import json

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"
MAX_DETAILED_ACTIVITIES = 50

def get_activity_id(act):
    raw_id = act.get("activityId") or act.get("startTimeLocal")
    return str(raw_id) if raw_id is not None else None

def fetch_activity_details(access_token, activity_id):
    url = f"https://personal.connectapi.garmin.com/activity-service/activity/{activity_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
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

    all_activities = []
    start, limit = 0, 100

    while True:
        search_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start={start}&limit={limit}"
        req = urllib.request.Request(search_url, headers={"Authorization": f"Bearer {access_token}"})
        with urllib.request.urlopen(req) as r:
            batch = json.loads(r.read().decode("utf-8"))
            if isinstance(batch, dict):
                batch = batch.get("activityList", [])
            if not batch:
                break
            all_activities.extend(batch)
            if len(batch) < limit:
                break
            start += limit

    all_activities.sort(key=lambda x: str(x.get("startTimeLocal", "")), reverse=True)

    print(f"Hämtar lapDTOs för de {MAX_DETAILED_ACTIVITIES} senaste passen...")
    for act in all_activities[:MAX_DETAILED_ACTIVITIES]:
        act_id = act.get("activityId")
        if act_id:
            details = fetch_activity_details(access_token, act_id)
            if details:
                # Extrahera lapDTOs direkt och lägg som egen nyckel
                if "lapDTOs" in details:
                    act["lapDTOs"] = json.dumps(details["lapDTOs"], ensure_ascii=False)
                if "splitSummaries" in details:
                    act["splitSummaries"] = json.dumps(details["splitSummaries"], ensure_ascii=False)

    raw_combined = {get_activity_id(a): a for a in all_activities if get_activity_id(a)}

    if os.path.exists(FILENAME):
        with open(FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act_id = get_activity_id(row)
                if act_id and act_id in raw_combined:
                    if not raw_combined[act_id].get("lapDTOs") and row.get("lapDTOs"):
                        raw_combined[act_id]["lapDTOs"] = row.get("lapDTOs")
                    if not raw_combined[act_id].get("splitSummaries") and row.get("splitSummaries"):
                        raw_combined[act_id]["splitSummaries"] = row.get("splitSummaries")
                elif act_id:
                    restored = {}
                    for k, v in row.items():
                        try:
                            restored[k] = json.loads(v)
                        except Exception:
                            restored[k] = v
                    raw_combined[act_id] = restored

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

    print(f"Klart! Sparat {len(raw_combined)} aktiviteter.")

if __name__ == "__main__":
    main()
