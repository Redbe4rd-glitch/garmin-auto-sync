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

    print("Hämtar aktiviteter från Garmin Personal API...")
    
    # Rätt endpoint enligt Garmins Swagger-specifikation för aktivitessökning
    url = "https://personal.connectapi.garmin.com/activitylist-service/activities/search/activities?start=0&limit=30"
    
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"ApiKey {API_KEY}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print(f"Kunde inte hämta data, statuskod: {response.status}")
                exit(1)
                
            data = response.read().decode("utf-8")
            activities_data = json.loads(data)

        # Spara till CSV-fil
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
