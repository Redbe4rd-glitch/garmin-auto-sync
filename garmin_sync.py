import os
import csv
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta

API_KEY = os.getenv("GARMIN_API_KEY")
ACTIVITIES_FILENAME = "garmin_activities.csv"
HEALTH_FILENAME = "garmin_health.csv"
MAX_DETAILED_ACTIVITIES = 50
HEALTH_DAYS = 30  # Antal dagar tillbaka att hämta dygnet-runt-data för

def get_activity_id(act):
    raw_id = act.get("activityId") or act.get("startTimeLocal")
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
    """Hämtar dygnet-runt-data (vilopuls, HRV, sömn, stress) och sparar till garmin_health.csv."""
    print(f"Hämtar dygnet-runt- och hälsodata för de senaste {HEALTH_DAYS} dagarna...")
    
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(HEALTH_DAYS)]
    
    health_records = {}

    # Läs in befintlig hälsodata om filen finns för att bevara historik
    if os.path.exists(HEALTH_FILENAME):
        with open(HEALTH_FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date"):
                    health_records[row["date"]] = row

    for date_str in dates:
        # 1. Daglig sammanfattning (Vilopuls & Body Battery)
        summary_url = f"https://personal.connectapi.garmin.com/usersummary-service/usersummary/daily/{date_str}"
        summary_data = fetch_garmin_api(summary_url, access_token) or {}

        # 2. HRV-data
        hrv_url = f"https://personal.connectapi.garmin.com/hrv-service/hrv/{date_str}"
        hrv_data = fetch_garmin_api(hrv_url, access_token) or {}

        # 3. Sömndata
        sleep_url = f"https://personal.connectapi.garmin.com/sleep-service/sleep/dailySleep?date={date_str}"
        sleep_data = fetch_garmin_api(sleep_url, access_token) or {}

        # --- Robust utläsning av mätvärden ---
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

        # Uppdatera eller lägg till ny rad
        if date_str not in health_records:
            health_records[date_str] = record
        else:
            for k, v in record.items():
                if v != "" or k not in health_records[date_str]:
                    health_records[date_str][k] = v

    fieldnames = ["date", "restingHeartRate", "hrvStatus", "hrvWeeklyAvg", "sleepScore", "sleepTimeSeconds", "deepSleepSeconds", "bodyBattery"]
    
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

    # 1. Hämta token via Personal API
    token_url = "https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token"
    token_req = urllib.request.Request(
        token_url,
        data=b"",
        headers={"Authorization": f"ApiKey {API_KEY}"},
        method="POST"
    )

    with urllib.request.urlopen(token_req) as resp:
        access_token = resp.read().decode("utf-8").strip()

    # 2. Synka Dygnet-runt & Hälsodata
    sync_health_data(access_token)

    # 3. Hämta aktivitetslistan
    all_activities = []
    start, limit = 0, 100

    while True:
        search_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start={start}&limit={limit}"
        batch = fetch_garmin_api(search_url, access_token)
        if not batch:
            break
        if isinstance(batch, dict):
            batch = batch.get("activityList", [])
        if not batch:
            break
        all_activities.extend(batch)
        if len(batch) < limit:
            break
        start += limit

    all_activities.sort(key=lambda x: str(x.get("startTimeLocal", "")), reverse=True)

    # 4. Hämta detaljer (splitSummaries) för de senaste passen
    print(f"Hämtar faser och intervaller (splitSummaries) för de {MAX_DETAILED_ACTIVITIES} senaste passen...")
    for act in all_activities[:MAX_DETAILED_ACTIVITIES]:
        act_id = act.get("activityId")
        if act_id:
            details = fetch_activity_details(access_token, act_id)
            if details:
                act.update(details)
                if "splitSummaries" in details:
                    act["splitSummaries"] = json.dumps(details["splitSummaries"], ensure_ascii=False)

    raw_combined = {get_activity_id(a): a for a in all_activities if get_activity_id(a)}

    # 5. Bevara tidigare sparad data i CSV för aktiviteter
    if os.path.exists(ACTIVITIES_FILENAME):
        with open(ACTIVITIES_FILENAME, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                act_id = get_activity_id(row)
                if act_id and act_id in raw_combined:
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

    # 6. Skriv aktiviteter till garmin_activities.csv
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

    print(f"Klart! Sparade {len(raw_combined)} aktiviteter i {ACTIVITIES_FILENAME}.")

if __name__ == "__main__":
    main()
