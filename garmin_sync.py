import os
import csv
import urllib.request
import urllib.error
import json

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"

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

        print("Autentisering lyckades! Hämtar all aktivitetsdata...")

        # Ökar limit till 100 för att få med mer historik på en gång
        activities_url = "https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start=0&limit=100"
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

        activities = activities_data if isinstance(activities_data, list) else activities_data.get("activityList", [])
        
        if not activities:
            print("Inga aktiviteter hittades.")
            return

        # Dynamiskt: Samla in ALLA unika nycklar som finns i Garmins data
        fieldnames = set()
        for act in activities:
            fieldnames.update(act.keys())
        fieldnames = sorted(list(fieldnames))

        # Spara all data till CSV-filen
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Skriv alla hittade fältnamn som rubriker
            writer.writerow(fieldnames)
            
            for act in activities:
                row = []
                for field in fieldnames:
                    val = act.get(field, "")
                    # Om värdet är ett objekt eller en lista, gör om det till textformaterad JSON
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    row.append(val)
                writer.writerow(row)
                
        print(f"All data ({len(fieldnames)} unika kolumner) för {len(activities)} aktiviteter har sparats till {FILENAME}!")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP-fel {e.code}: {e.reason} - Detaljer: {error_body}")
        exit(1)
    except Exception as err:
        print(f"Ett fel uppstod vid anropet: {err}")
        exit(1)

if __name__ == "__main__":
    main()
