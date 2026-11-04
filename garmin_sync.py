import os
import csv
from datetime import datetime
from garmin_connect_personal_api import GarminPersonalApiClient

API_KEY = os.getenv("GARMIN_API_KEY")
FILENAME = "garmin_activities.csv"

def main():
    if not API_KEY:
        print("Fel: GARMIN_API_KEY saknas i miljövariablerna.")
        exit(1)

    print("Ansluter till Garmin Personal API...")
    try:
        # Skapa klienten direkt med API-nyckeln (biblioteket sköter token-växlingen internt)
        with GarminPersonalApiClient(api_key=API_KEY) as client:
            print("Anslutning lyckades! Hämtar aktiviteter...")
            
            # Hämta aktiviteter via standardmetoden i biblioteket
            activities_data = client.search_activities(start=0, limit=30)
            
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
        print(f"Ett fel uppstod: {err}")
        exit(1)

if __name__ == "__main__":
    main()
