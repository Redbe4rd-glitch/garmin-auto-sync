import os
import csv
from datetime import datetime
from garminconnect import Garmin

# Hämta inloggningsuppgifter från GitHub Secrets
EMAIL = os.getenv("GARMIN_EMAIL")
PASSWORD = os.getenv("GARMIN_PASSWORD")
FILENAME = "garmin_activities.csv"

def main():
    print("Loggar in på Garmin Connect...")
    try:
        api = Garmin(EMAIL, PASSWORD)
        api.login()
        print("Inloggning lyckades!")
        
        # Hämta de 30 senaste aktiviteterna
        print("Hämtar senaste aktiviteter...")
        activities = api.get_activities(0, 30)
        
        # Skriva till CSV-fil
        file_exists = os.path.exists(FILENAME)
        
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Skriv rubriker
            writer.writerow(["Datum", "Aktivitet", "Tid (min)", "Sträcka (km)", "Puls (snitt)", "Kalorier"])
            
            for act in activities:
                date = act.get("startTimeLocal", "")[:10]
                name = act.get("activityName", "Aktivitet")
                duration = round(act.get("duration", 0) / 60, 1)
                distance = round(act.get("distance", 0) / 1000, 2)
                hr = act.get("averageHR", "N/A")
                calories = act.get("calories", 0)
                
                writer.writerow([date, name, duration, distance, hr, calories])
                
        print(f"Aktiviteter sparade till {FILENAME}!")

    except Exception as err:
        print(f"Ett fel uppstod: {err}")
        exit(1)

if __name__ == "__main__":
    main()
