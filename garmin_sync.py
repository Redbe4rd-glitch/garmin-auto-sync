import os
import csv
import urllib.request
import urllib.error
import json

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"

def get_activity_id(act):
    """Hämtar unikt ID som sträng för säker jämförelse utan dubbletter."""
    raw_id = act.get("activityId") or act.get("startTimeLocal")
    return str(raw_id) if raw_id is not None else None

def fetch_activity_details(access_token, activity_id):
    """Hämtar detaljerad information inklusive laps/splits för en specifik aktivitet."""
    details_url = f"https://personal.connectapi.garmin.com/activity-service/activity/{activity_id}"
    req = urllib.request.Request(
        details_url,
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
        print("Fel: GARMIN_API_KEY saknas i miljövariablerna.")
        exit(1)

    print("Autentiserar mot Garmin Personal API...")
    
    token_url = "https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token"
    token_req = urllib.request.Request(
        token_url,
        data=b"",
        headers={
            "Authorization": f"ApiKey {API_KEY}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(token_req) as token_response:
            raw_response = token_response.read().decode("utf-8").strip()
            if not raw_response:
                print("Fel: Tomt svar från token-endpointen.")
                exit(1)
            access_token = raw_response

        print("Autentisering lyckades! Hämtar all aktivitetsdata med paginering...")

        # 1. Hämta alla aktiviteter från API:et (översikt)
        all_activities = []
        start = 0
        limit = 100

        while True:
            activities_url = f"https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start={start}&limit={limit}"
            act_req = urllib.request.Request(
                activities_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
            )

            with urllib.request.urlopen(act_req) as act_response:
                act_raw = act_response.read().decode("utf-8")
                activities_data = json.loads(act_raw)

            batch = activities_data if isinstance(activities_data, list) else activities_data.get("activityList", [])
            
            if not batch:
                break
                
            all_activities.extend(batch)
            print(f"Hämtade {len(batch)} aktiviteter (totalt hittills: {len(all_activities)})...")
            
            if len(batch) < limit:
                break
            start += limit

        # 2. Hämta detaljerad data (inklusive laps/splits) för varje aktivitet
        print("Hämtar detaljerade varv och splits per aktivitet...")
        for act in all_activities:
            act_id = act.get("activityId")
            if act_id:
                details = fetch_activity_details(access_token, act_id)
                if details:
                    # Slå ihop detaljerna med aktivitetsdatat
                    act.update(details)
                    # Säkerställ att laps/lapSummaries finns som strängifierad JSON i egna fält
                    if "lapDTOs" in details:
                        act["laps"] = json.dumps(details["lapDTOs"], ensure_ascii=False)
                    elif "splits" in details:
                        act["laps"] = json.dumps(details["splits"], ensure_ascii=False)

        # Map för att lagra alla unika pass (ID som sträng)
        raw_combined = {}

        for act in all_activities:
            act_id = get_activity_id(act)
            if act_id:
                raw_combined[act_id] = act

        # 3. Läs in och slå ihop med befintlig CSV-fil (om den finns)
        if os.path.exists(FILENAME):
            print(f"Läser in befintlig historik från {FILENAME} för att förhindra dubbletter...")
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

        if not raw_combined:
            print("Inga aktiviteter hittades.")
            return

        # 4. Bygg gemensam kolumnlista från alla unika nycklar
        fieldnames = set()
        for act in raw_combined.values():
            fieldnames.update(act.keys())
        fieldnames = sorted(list(fieldnames))

        # 5. Spara rensad data tillbaka till CSV
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            
            sorted_acts = sorted(
                raw_combined.values(), 
                key=lambda x: str(x.get("startTimeLocal", "")), 
                reverse=True
            )

            for act in sorted_acts:
                row = []
                for field in fieldnames:
                    val = act.get(field, "")
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    row.append(val)
                writer.writerow(row)
                
        print(f"Klart! Totalt {len(raw_combined)} unika aktiviteter sparades till {FILENAME} med komplett lap-data.")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP-fel {e.code}: {e.reason} - Detaljer: {error_body}")
        exit(1)
    except Exception as err:
        print(f"Ett fel uppstod vid anropet: {err}")
        exit(1)

if __name__ == "__main__":
    main()
