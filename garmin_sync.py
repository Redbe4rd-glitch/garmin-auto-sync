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

        print("Autentisering lyckades! Hämtar all aktivitetsdata med paginering...")

        # 1. Hämta alla aktiviteter genom att loopa tills listan är tom
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

        if not all_activities:
            print("Inga aktiviteter hittades från API:et.")
            return

        # Konvertera nya API-data till en dictionary med unikt ID som nyckel för att undvika dubbletter
        new_activities_dict = {}
        for act in all_activities:
            # Använd 'activityId' som unikt ID om det finns, annars 'startTimeLocal'
            act_id = act.get("activityId") or act.get("startTimeLocal")
            new_activities_dict[act_id] = act

        # 2. Läs in befintlig CSV-fil om den redan finns (för att bevara historik)
        existing_activities_dict = {}
        if os.path.exists(FILENAME):
            print(f"Läser in befintlig historik från {FILENAME}...")
            with open(FILENAME, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Försök hitta id-kolumnen
                    act_id = row.get("activityId") or row.get("startTimeLocal")
                    if act_id:
                        # Konvertera tillbaks JSON-strängar till listor/dicts om det behövs vid sammanslagning, 
                        # men enklast är att lagra raderna direkt.
                        existing_activities_dict[act_id] = row

            print(f"Hittade {len(existing_activities_dict)} tidigare sparade aktiviteter.")

        # 3. Slå ihop: nya aktiviteter uppdaterar eller läggs till till de gamla
        # Vi bygger en gemensam pool av råa aktivitetsobjekt om möjligt, annars slår vi ihop på dict-nivå.
        # Enklaste robustasättet: Låt alla ID:n från API (nyare data) ersätta gamla, och behåll gamla som inte finns i API.
        combined_dict = {**existing_activities_dict}
        
        # För att dynamiskt kunna skriva ut alla kolumner samlar vi in alla unika nycklar från ALLA aktiviteter
        fieldnames = set()
        
        # Omvandla tillbaka till en gemensam lista av dicts för fältanalys
        final_activities_list = []
        
        # Uppdatera med ny data (här sparar vi de råa dictsen från Garmin i en map)
        raw_combined = {}
        for row in existing_activities_dict.values():
            # Återskapa lite struktur om nödvändigt, eller hantera dem som dicts
            pass
            
        # Säkraste metoden för att bygga på utan att tappa historik:
        # Vi sparar undan allt från API:et, och lägger till rader från gamla CSV om de saknas i API-svaret.
        # (Om ditt API alltid returnerar hela historiken upp till 100+ så täcker loopen allt).
        
        for act in all_activities:
            act_id = act.get("activityId") or act.get("startTimeLocal")
            raw_combined[act_id] = act

        # Lägg till gamla som inte finns med i dagens API-batch (om API:et har en gräns bakåt)
        if os.path.exists(FILENAME):
            with open(FILENAME, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    act_id = row.get("activityId") or row.get("startTimeLocal")
                    if act_id and act_id not in raw_combined:
                        # Detta är ett äldre pass som inte kom med i den nya batch-sökningen
                        # Vi rekonstruerar det till dict
                        restored = {}
                        for k, v in row.items():
                            try:
                                restored[k] = json.loads(v)
                            except:
                                restored[k] = v
                        raw_combined[act_id] = restored

        # Samla in ALLA unika nycklar över alla pass
        for act in raw_combined.values():
            fieldnames.update(act.keys())
        fieldnames = sorted(list(fieldnames))

        # 4. Spara till CSV
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            
            # Sortera gärna efter starttid om fältet finns
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
                
        print(f"Klart! Totalt {len(raw_combined)} unika aktiviteter sparade till {FILENAME}.")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTP-fel {e.code}: {e.reason} - Detaljer: {error_body}")
        exit(1)
    except Exception as err:
        print(f"Ett fel uppstod vid anropet: {err}")
        exit(1)

if __name__ == "__main__":
    main()
