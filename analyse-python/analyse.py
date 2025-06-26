import boto3
from boto3.dynamodb.types import TypeDeserializer
from collections import defaultdict

# Initialize DynamoDB client and deserializer
dynamodb = boto3.client('dynamodb')
deserializer = TypeDeserializer()

def deserialize_dynamodb_item(item):
    return {k: deserializer.deserialize(v) for k, v in item.items()}

def process_member(member, reports):
    first = member.get('firstName', '')
    last = member.get('lastName', '')
    name = f"{first} {last}".strip()
    gender = member.get('gender', 'Unknown')
    mobile = member.get('mobile', '')
    stay = member.get('stayAtHall', False)
    cot = member.get('cotRequired', False)
    special_req = member.get('specialRequests', '').strip()
    recordings = member.get('recordingsNeeded', '').strip()
    difficulty = member.get('difficultyClimbingStairs', False)
    local_assist = member.get('localAssistance', '').strip()
    dates = member.get('attendingDates', [])
    meals = member.get('mealPreferences', {})

    # Report 1: Daily Participants
    for d in dates:
        dp = reports['daily_participants'][d]
        dp['total'] += 1
        dp['gender_counts'][gender] += 1
        dp['names'].append((name, gender))

    # Report 2: Venue Stay & Cots
    for d in dates:
        ds = reports['daily_stay'][d]
        if stay:
            ds['staying_total'] += 1
            ds['staying_gender'][gender] += 1
            if cot:
                ds['cots_total'] += 1
                ds['cots_gender'][gender] += 1
                ds['cot_names'].append((name, gender))

    # Report 3: Daily Meals & Beverages
    for d, p in meals.items():
        dm = reports['daily_meals'][d]
        # Meal counts
        for key, label in [
            ('breakfast', 'Breakfast'),
            ('lunch',     'Lunch'),
            ('highTea',   'High Tea'),
            ('dinner',    'Dinner'),
            ('packedFood','Packed Food')
        ]:
            if p.get(key, False):
                dm['meals'][label] += 1
        # Beverages
        bev_pref = p.get('teaCoffeePreference', 'none')
        sugar    = p.get('teaCoffeeSugar', 'none')
        if bev_pref == 'tea':
            dm['beverages']['Tea'][sugar] += 1
        elif bev_pref == 'coffee':
            dm['beverages']['Coffee'][sugar] += 1
        elif bev_pref == 'both':
            dm['beverages']['Tea'][sugar] += 1
            dm['beverages']['Coffee'][sugar] += 1
        else:
            dm['beverages']['None']['none'] += 1

    # Report 4: Special Assistance
    if special_req:
        reports['assistance'].append({'name': name, 'mobile': mobile, 'request': special_req})

    # Report 5: Recordings Requests
    if recordings:
        reports['recordings'].append({'name': name, 'mobile': mobile, 'recordings': recordings})

    # Report 6: Travel Assistance
    if difficulty or local_assist:
        ta = reports['travel_assist']
        ta['count'] += 1
        ta['gender_counts'][gender] += 1
        ta['people'].append({
            'name': name,
            'mobile': mobile,
            'difficulty': difficulty,
            'local_assist': local_assist
        })


def generate_reports(table_name):
    reports = {
        'daily_participants': defaultdict(lambda: {'total': 0, 'gender_counts': defaultdict(int), 'names': []}),
        'daily_stay': defaultdict(lambda: {
            'staying_total': 0,
            'staying_gender': defaultdict(int),
            'cots_total': 0,
            'cots_gender': defaultdict(int),
            'cot_names': []
        }),
        'daily_meals': defaultdict(lambda: {
            'meals': defaultdict(int),
            'beverages': defaultdict(lambda: defaultdict(int))
        }),
        'assistance': [],
        'recordings': [],
        'travel_assist': {'count': 0, 'gender_counts': defaultdict(int), 'people': []}
    }

    paginator = dynamodb.get_paginator('scan')
    for page in paginator.paginate(TableName=table_name):
        for item in page['Items']:
            data    = deserialize_dynamodb_item(item)
            members = data.get('travelDetails', {}).get('members', [])
            for m in members:
                process_member(m, reports)

    return reports


def print_reports(r):
    # Report 1
    print("\n" + "="*60)
    print("REPORT 1: DAILY PARTICIPANTS")
    print("="*60)
    for d in sorted(r['daily_participants']):
        dp = r['daily_participants'][d]
        print(f"\nDate: {d}")
        print(f"  Total: {dp['total']}")
        for g,c in dp['gender_counts'].items(): print(f"    {g}: {c}")
        print("  Names:")
        for n,g in dp['names']: print(f"    - {n} ({g})")

    # Report 2
    print("\n" + "="*60)
    print("REPORT 2: VENUE STAY & COTS")
    print("="*60)
    for d in sorted(r['daily_stay']):
        ds = r['daily_stay'][d]
        print(f"\nDate: {d}")
        print(f"  Staying: {ds['staying_total']}")
        for g,c in ds['staying_gender'].items(): print(f"    {g}: {c}")
        print(f"  Cots: {ds['cots_total']}")
        for g,c in ds['cots_gender'].items(): print(f"    {g}: {c}")
        print("  Names (cot):")
        for n,g in ds['cot_names']: print(f"    - {n} ({g})")

    # Report 3
    print("\n" + "="*60)
    print("REPORT 3: DAILY MEALS & BEVERAGES")
    print("="*60)
    for d in sorted(r['daily_meals']):
        dm = r['daily_meals'][d]
        print(f"\nDate: {d}")
        print("  Meals:")
        for m,c in dm['meals'].items(): print(f"    {m}: {c}")
        print("  Beverages:")
        for bev,sugars in dm['beverages'].items():
            tot = sum(sugars.values())
            print(f"    {bev}: {tot}")
            for s,cnt in sugars.items(): print(f"      {s}: {cnt}")

    # Report 4
    print("\n" + "="*60)
    print("REPORT 4: SPECIAL ASSISTANCE")
    print("="*60)
    for e in r['assistance']:
        print(f"Name: {e['name']} | Mobile: {e['mobile']} | Req: {e['request']}")

    # Report 5
    print("\n" + "="*60)
    print("REPORT 5: RECORDINGS REQUESTS")
    print("="*60)
    for e in r['recordings']:
        print(f"Name: {e['name']} | Mobile: {e['mobile']} | Recordings: {e['recordings']}")

    # Report 6
    print("\n" + "="*60)
    print("REPORT 6: TRAVEL ASSISTANCE")
    print("="*60)
    ta = r['travel_assist']
    print(f"Total needing assistance: {ta['count']}")
    for g,c in ta['gender_counts'].items(): print(f"  {g}: {c}")
    print("People:")
    for p in ta['people']:
        print(f"  - {p['name']} ({p['mobile']}) | DifficultyStairs: {p['difficulty']} | LocalAssist: {p['local_assist']}")

if __name__ == "__main__":
    TABLE_NAME = "users"
    reports = generate_reports(TABLE_NAME)
    print_reports(reports)
