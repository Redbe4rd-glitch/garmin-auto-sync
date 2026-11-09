import os
import csv
import urllib.request
import urllib.error
import json
import time
from datetime import datetime, timedelta

API_KEY = os.getenv("GARMIN_API_KEY")
ACTIVITIES_FILENAME = "garmin_activities.csv"
HEALTH_FILENAME = "garmin_health.csv"
MAX_DETAILED_ACTIVITIES = 20  # Räcker med de 20 senaste för detaljer/faser
HEALTH_DAYS = 30  # Antal dagar tillbaka att hämta dygnet-runt-data för

def get_activity_id(act):
    raw_id = act.get("activityId") or act.get("startTimeLocal") or act.get("Datum")
    return str(raw_id) if raw_id is not None else None

def fetch_garmin_api(url, access_token):
    """Hjälpfunktion för GET-anrop mot Garmin Connect Personal API."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Kunde inte hämta data från {url}: {e}")
        return None

def fetch_activity_details(access_token, activity_id):
    """Hämtar detaljerad information inklusive splitSummaries för ett pass."""
    url = f"https://personal.connectapi.garmin.com/activity-service/activity/{activity_id}"
    res = fetch_garmin_api(url, access_token)
    return res if res else {}

def sync_health_data(access_token):
    """Hämtar dygnet-runt-data (vilopuls, HRV, sömn) och sparar till garmin_health.csv."""
    print(f"Hämtar dygnet-runt- och hälsodata för de senaste {HEALTH_DAYS} dagarna...")
    
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(HEALTH_DAYS)]
    
    health_records = {}

    if os.path.exists(HEALTH_FILENAME):
        with open(HEALTH_FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date"):
                    health_records[row["date"]] = row

    for date_str in dates:
        summary_url = f"https://personal.connectapi.garmin.com/usersummary-service/usersummary/daily?calendarDate={date_str}"
        summary_data = fetch_garmin_api(summary_url, access_token) or {}

        hrv_url = f"https://personal.connectapi.garmin.com/hrv-service/hrv/{date_str}"
        hrv_data = fetch_garmin_api(hrv_url, access_token) or {}

        sleep_url = f"https://personal.connectapi.garmin.com/sleep-service/sleep/dailySleep?date={date_str}"
        sleep_data = fetch_garmin_api(sleep_url, access_token) or {}

        if isinstance(summary_data, list) and len(summary_data) > 0:
            summary_data = summary_data[0]

        rhr = (
            summary_data.get("restingHeartRate") or 
            summary_data.get("rhr") or 
            summary_data.get("userDailySummary", {}).get("restingHeartRate") or
            ""
        )
        
        body_battery = (
            summary_data.get("bodyBatteryMostRecentValue") or 
            summary_data.get("bodyBattery") or 
            summary_data.get("userDailySummary", {}).get("bodyBatteryMostRecentValue") or 
            ""
        )
        
        hrv_summary = hrv_data.get("hrvSummary") or hrv_data or {}
        hrv_status = hrv_summary.get("status") or ""
        hrv_weekly_avg = hrv_summary.get("weeklyAvg") or ""

        sleep_dto = sleep_data.get("dailySleepDTO") or sleep_data or {}
        sleep_scores = sleep_dto.get("sleepScores") or sleep_dto.get("sleepScore") or {}
        
        sleep_overall = ""
        if isinstance(sleep_scores, dict):
            overall = sleep_scores.get("overallScore") or sleep_scores.get("overall")
            if isinstance(overall, dict):
                sleep_overall = overall.get("value") or ""
            elif isinstance(overall, (int, float, str)):
                sleep_overall = overall
        elif isinstance(sleep_scores, (int, float, str)):
            sleep_overall = sleep_scores

        deep_sleep_sec = sleep_dto.get("deepSleepSeconds") or ""
        sleep_time_sec = sleep_dto.get("sleepTimeSeconds") or ""

        record = {
            "date": date_str,
            "restingHeartRate": rhr,
            "hrvStatus": hrv_status,
            "hrvWeeklyAvg": hrv_weekly_avg,
            "sleepScore": sleep_overall,
            "sleepTimeSeconds": sleep_time_sec,
            "deepSleepSeconds": deep_sleep_sec,
            "bodyBattery": body_battery
        }

        if date_str not in health_records:
            health_records[date_str] = record
        else:
            for k, v in record.items():
                if v != "" or k not in health_records[date_str]:
                    health_records[date_str][k] = v
        
        time.sleep(0.1)

    fieldnames = [
        "date", "restingHeartRate", "hrvStatus", "hrvWeeklyAvg", 
        "sleepScore", "sleepTimeSeconds", "deepSleepSeconds", "bodyBattery",
        "rpe", "painLocation", "painLevel"
    ]
    
    sorted_records = sorted(health_records.values(), key=lambda x: x["date"], reverse=True)
    
    with open(HEALTH_FILENAME, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_records)

    print(f"Hälsodata sparad till {HEALTH_FILENAME} ({len(sorted_records)} rader).")

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

    # 1. Synka Hälsa
    sync_health_data(access_token)

    # 2. Läs in ALLA tidigare sparade aktiviteter från CSV först (så vi behåller historiken)
    raw_combined = {}
    if os.path.exists(ACTIVITIES_FILENAME):
        with open(ACTIVITIES_FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act_id = get_activity_id(row)
                if act_id:
                    # Återskapa ev. JSON-strukturer
                    restored = {}
                    for k, v in row.items():
                        try:
                            restored[k] = json.loads(v)
                        except Exception:
                            restored[k] = v
                    raw_combined[act_id] = restored

    # 3. Hämta enbart de senaste 50-100 passen från Garmin (snabbt och effektivt)
    print("Hämtar senaste aktiviteter från Garmin...")
    search_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start=0&limit=50"
    batch = fetch_garmin_api(search_url, access_token)
    
    recent_activities = []
    if batch:
        if isinstance(batch, dict):
            batch = batch.get("activityList", [])
        recent_activities.extend(batch)

    print(f"Hämtade {len(recent_activities)} pass från Garmin. Uppdaterar detaljer...")

    # 4. Hämta detaljer (splitSummaries) ENDAST för nya pass som saknar det
    print(f"Kontrollerar detaljer och faser för nya pass...")
    for act in recent_activities[:MAX_DETAILED_ACTIVITIES]:
        act_id = get_activity_id(act)
        if act_id:
            # Om passet redan finns sparat och har splitSummaries, hoppa över API-anropet!
            if act_id in raw_combined and raw_combined[act_id].get("splitSummaries"):
                continue
                
            print(f"Hämtar nya detaljer för pass ID: {act_id}...")
            details = fetch_activity_details(access_token, act_id)
            if details:
                act.update(details)
                if "splitSummaries" in details:
                    act["splitSummaries"] = json.dumps(details["splitSummaries"], ensure_ascii=False)
            time.sleep(0.5)  # Säker paus mellan anropen

    # 5. Lägg till/uppdatera de nyhämtade passen i vår gemensamma samling
    for act in recent_activities:
        act_id = get_activity_id(act)
        if act_id:
            # Om passet redan finns, behåll ev. tidigare splitSummaries om nya saknas
            if act_id in raw_combined and not act.get("splitSummaries") and raw_combined[act_id].get("splitSummaries"):
                act["splitSummaries"] = raw_combined[act_id].get("splitSummaries")
            raw_combined[act_id] = act

    # Hämta alla unika fältnamn över alla pass
    fieldnames = sorted(list(set(k for a in raw_combined.values() for k in a.keys())))

    # 6. Skriv tillbaka till garmin_activities.csv
    with open(ACTIVITIES_FILENAME, mode="w", newline="", encoding="utf-8") as f:
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

    print(f"Klart! Sparade totalt {len(raw_combined)} aktiviteter i {ACTIVITIES_FILENAME}.")

if __name__ == "__main__":
    main()
