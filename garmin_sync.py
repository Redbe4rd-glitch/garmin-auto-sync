import os
import csv
import urllib.request
import urllib.error
import json
import io

# Importera fitparse (kräver: pip install fitparse)
try:
    import fitparse
except ImportError:
    fitparse = None

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"
MAX_DETAILED_ACTIVITIES = 20  # Begränsa nedladdning av .FIT-filer för att undvika timeout

def get_activity_id(act):
    raw_id = act.get("activityId") or act.get("startTimeLocal")
    return str(raw_id) if raw_id is not None else None

def fetch_fit_file(access_token, activity_id):
    """Laddar ner original-.FIT-filen för ett pass."""
    url = f"https://personal.connectapi.garmin.com/download-service/files/activity/{activity_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except Exception as e:
        print(f"Kunde inte hämta .FIT-fil för pass {activity_id}: {e}")
        return None

def parse_laps_from_fit(fit_data):
    """Extraherar kilometer-laps och löpdynamik från en .FIT-fil."""
    if not fitparse or not fit_data:
        return []

    try:
        fitfile = fitparse.FitFile(io.BytesIO(fit_data))
        laps = []
        for record in fitfile.get_messages('lap'):
            lap_data = {}
            for data in record:
                if data.value is not None:
                    lap_data[data.name] = data.value
            
            # Formatera och mappa ut relevanta mätvärden per km/lap
            laps.append({
                "duration": lap_data.get("total_timer_time") or lap_data.get("total_elapsed_time"),
                "distance": lap_data.get("total_distance"),
                "averageSpeed": lap_data.get("avg_speed") or lap_data.get("enhanced_avg_speed"),
                "maxSpeed": lap_data.get("max_speed") or lap_data.get("enhanced_max_speed"),
                "avgGroundContactTime": lap_data.get("avg_stance_time"),
                "avgGroundContactBalanceLeft": lap_data.get("avg_stance_time_balance"),
                "averageHR": lap_data.get("avg_heart_rate"),
                "maxHR": lap_data.get("max_heart_rate"),
                "avgCadence": lap_data.get("avg_running_cadence") or lap_data.get("avg_cadence")
            })
        return laps
    except Exception as e:
        print(f"Fel vid parsning av .FIT-fil: {e}")
        return []

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

    print(f"Hämtar och tolkar .FIT-filer för de {MAX_DETAILED_ACTIVITIES} senaste passen...")
    for act in all_activities[:MAX_DETAILED_ACTIVITIES]:
        act_id = act.get("activityId")
        if act_id:
            fit_bytes = fetch_fit_file(access_token, act_id)
            if fit_bytes:
                laps = parse_laps_from_fit(fit_bytes)
                if laps:
                    act["lapDTOs"] = json.dumps(laps, ensure_ascii=False)

    raw_combined = {get_activity_id(a): a for a in all_activities if get_activity_id(a)}

    if os.path.exists(FILENAME):
        with open(FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act_id = get_activity_id(row)
                if act_id and act_id in raw_combined:
                    if not raw_combined[act_id].get("lapDTOs") and row.get("lapDTOs"):
                        raw_combined[act_id]["lapDTOs"] = row.get("lapDTOs")
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
