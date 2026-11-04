import os
import csv
import urllib.request
import json
from datetime import datetime

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"

def main():
    if not API_KEY:
        print("Fel: GARMIN_API_KEY saknas i miljövariablerna.")
        exit(1)

    print("Autentiserar mot Garmin Personal API...")
    
    # Steg 1: Hämta access-token med din personliga API-nyckel enligt Swagger
    token_url = "https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token"
    token_req = urllib.request.Request(
        token_url,
        data=b"",  # POST-anrop med tom kropp
        headers={
            "Authorization": f"ApiKey {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(token_req) as token_response:
            if token_response.status != 200:
                print(f"Kunde inte autentisera, statuskod: {token_response.status}")
                exit(1)
            token_data = json.loads(token_response.read().decode("utf-8"))
            access_token = token_data.get("access_token")

        if not access_token:
            print("Fel: Ingen access_token hittades i svaret från Garmin.")
            exit(1)

        print("Autentisering lyckades! Hämtar aktiviteter...")

        # Steg 2: Använd access-token för att hämta aktiviteter från rätt Swagger-endpoint
        activities_url = "https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start=0&limit=30"
        act_req = urllib.request.Request(
            activities_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(act_req) as act_response:
            if act_response.status != 200:
                print(f"Kunde inte hämta aktiviteter, statuskod: {act_response.status}")
                exit(1)
            activities_data = json.loads(act_response.read().decode("utf-8"))

        # Steg 3: Spara till CSV-fil
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Datum", "Aktivitet", "Tid (min)", "Sträcka (km)", "Kalorier"])
            
            activities = activities_data if isinstance(activities_data, list) else activities_data.get("activityList", [])
            
            for act in activities:
                date = act.get("startTimeLocal", "")[:10]
                name = act.get("activityName", "Aktivitet")
                duration = round(float(act.get("duration", 0)) / 60, 1)
                distance = round(float(act.get("distance", 0)) / 1000, 2)
                calories = act.get("calories", 0)
                
                writer.writerow([date, name, duration, distance, calories])
                
        print(f"Aktiviteter sparade till {FILENAME}!")

    except Exception as err:
        print(f"Ett fel uppstod vid anropet: {err}")
        exit(1)

if __name__ == "__main__":
    main()
