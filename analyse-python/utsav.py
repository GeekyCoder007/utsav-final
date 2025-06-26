import boto3
from boto3.dynamodb.types import TypeDeserializer
from collections import defaultdict
from datetime import datetime

# --- Configuration ---
# Replace 'your_table_name' with your actual DynamoDB table name.
TABLE_NAME = "users"
DATES_OF_INTEREST = ["2025-07-08", "2025-07-09", "2025-07-10", "2025-07-11"]

# Initialize DynamoDB client and the deserializer to convert DynamoDB's format to standard Python dicts.
# Ensure your AWS credentials are configured (e.g., via environment variables or ~/.aws/credentials)
try:
    dynamodb = boto3.client('dynamodb')
    deserializer = TypeDeserializer()
except Exception as e:
    print(f"Error initializing boto3. Please check your AWS credentials configuration: {e}")
    exit()


def deserialize_item(item):
    """Converts a DynamoDB-formatted item into a regular Python dictionary."""
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def get_age_group(age):
    """Categorizes an age into a predefined group."""
    if age <= 12:
        return "Kids (0-12)"
    elif 13 <= age <= 30:
        return "Young (13-30)"
    elif 31 <= age <= 59:
        return "Middle-Aged (31-59)"
    else:
        return "Seniors (60+)"


def process_registrations(table_name):
    """
    Scans the DynamoDB table, processes each member's data, and aggregates it for reporting.
    """
    # This dictionary will hold all the aggregated data for our reports.
    reports = {
        'all_participants': {'total': 0, 'gender_counts': defaultdict(int), 'list': set()},
        'venue_stay': {
            'total_count': 0,
            'gender_total': defaultdict(int),
            'age_view': defaultdict(lambda: {'M': [], 'F': [], 'Unknown': []})
        },
        'meal_plan': {date: {
            'morning_tea': 0, 'morning_coffee': 0, 'morning_coffee_sugar': 0, 'morning_coffee_nosugar': 0,
            'breakfast': 0, 'lunch': 0, 'dinner': 0,
            'high_tea': 0, 'high_coffee': 0, 'high_tea_nosugar': 0, 'high_coffee_nosugar': 0
        } for date in DATES_OF_INTEREST},
        'cot_needs': defaultdict(lambda: {'total': 0, 'women': 0, 'men': 0, 'list': []}),
        'travel_assistance': {'total': 0, 'gender_counts': defaultdict(int), 'list': []}
    }

    paginator = dynamodb.get_paginator('scan')

    try:
        # Iterate through all items in the DynamoDB table.
        for page in paginator.paginate(TableName=table_name):
            for item in page.get('Items', []):
                data = deserialize_item(item)
                members = data.get('travelDetails', {}).get('members', [])

                for member in members:
                    # --- Extract Member Details ---
                    first_name = member.get('firstName', '')
                    last_name = member.get('lastName', '')
                    name = f"{first_name} {last_name}".strip()
                    mobile = member.get('mobile', 'N/A')
                    gender = member.get('gender', 'Unknown')
                    age = int(member.get('age', 0))

                    # --- 1. All Participants Report ---
                    if (name, mobile) not in reports['all_participants']['list']:
                        reports['all_participants']['list'].add((name, mobile))
                        reports['all_participants']['gender_counts'][gender] += 1

                    # --- 2. Venue Stay Report ---
                    if member.get('stayAtHall', False):
                        reports['venue_stay']['total_count'] += 1
                        reports['venue_stay']['gender_total'][gender] += 1
                        age_group = get_age_group(age)
                        reports['venue_stay']['age_view'][age_group][gender].append(
                            {'name': name, 'contact': mobile, 'age': age})

                    # --- 3. Meal Plan Report ---
                    attending = member.get('attendingDates', [])
                    meals = member.get('mealPreferences', {})
                    for date in attending:
                        if date in DATES_OF_INTEREST:
                            plan = reports['meal_plan'][date]

                            # Morning Beverages
                            morning_bev = member.get('morningTeaCoffee', {})
                            if morning_bev.get('preference') in ['tea', 'both']:
                                plan['morning_tea'] += 1
                            if morning_bev.get('preference') in ['coffee', 'both']:
                                plan['morning_coffee'] += 1
                                if morning_bev.get('sugar') == 'sugar':
                                    plan['morning_coffee_sugar'] += 1
                                else:
                                    plan['morning_coffee_nosugar'] += 1

                            # Daily Meals & High Tea
                            daily_meal_prefs = meals.get(date, {})
                            if daily_meal_prefs.get('breakfast'): plan['breakfast'] += 1
                            if daily_meal_prefs.get('lunch'): plan['lunch'] += 1
                            if daily_meal_prefs.get('dinner'): plan['dinner'] += 1

                            # High Tea Beverages
                            if daily_meal_prefs.get('highTea'):
                                tea_pref = daily_meal_prefs.get('teaCoffeePreference', 'none')
                                sugar_pref = daily_meal_prefs.get('teaCoffeeSugar', 'none')
                                if tea_pref in ['tea', 'both']:
                                    plan['high_tea'] += 1
                                    if sugar_pref != 'sugar': plan['high_tea_nosugar'] += 1
                                if tea_pref in ['coffee', 'both']:
                                    plan['high_coffee'] += 1
                                    if sugar_pref != 'sugar': plan['high_coffee_nosugar'] += 1

                    # --- 4. Cot Needs Report ---
                    if member.get('stayAtHall', False) and member.get('cotRequired', False):
                        for date in attending:
                            cot_report = reports['cot_needs'][date]
                            cot_report['total'] += 1
                            if gender == 'M':
                                cot_report['men'] += 1
                            elif gender == 'F':
                                cot_report['women'] += 1
                            cot_report['list'].append({'name': name, 'contact': mobile})

                    # --- 5. Travel Assistance Report ---
                    if member.get('difficultyClimbingStairs', False) or member.get('localAssistance'):
                        reports['travel_assistance']['total'] += 1
                        reports['travel_assistance']['gender_counts'][gender] += 1
                        reports['travel_assistance']['list'].append({'name': name, 'contact': mobile, 'age': age})

    except Exception as e:
        print(f"An error occurred while scanning DynamoDB table '{table_name}': {e}")
        return None

    # Update total participant count at the end
    reports['all_participants']['total'] = len(reports['all_participants']['list'])
    return reports


def print_final_reports(reports):
    """
    Prints all the generated reports in a clean, user-friendly format.
    """
    if not reports:
        print("Could not generate reports due to an error.")
        return

    # --- REPORT 1: ALL PARTICIPANTS ---
    print("\n" + "=" * 80)
    print("REPORT 1: ALL PARTICIPANTS LIST")
    print("=" * 80)
    p_report = reports['all_participants']
    print(f"\nTotal Unique Participants: {p_report['total']}")
    print("Gender Bifurcation:")
    for gender, count in p_report['gender_counts'].items():
        print(f"  - {gender}: {count}")
    print("\nList of Participants:")
    for name, contact in sorted(list(p_report['list'])):
        print(f"  - Name: {name}, Contact: {contact}")

    # --- REPORT 2: VENUE STAY DETAILS ---
    print("\n" + "=" * 80)
    print("REPORT 2: VENUE STAY & ACCOMMODATION")
    print("=" * 80)
    v_report = reports['venue_stay']
    print(f"\nTotal People Staying at Venue: {v_report['total_count']}")
    print("Gender-wise Total:")
    for gender, count in v_report['gender_total'].items():
        print(f"  - {gender}: {count}")
    print("\nAge-wise & Gender-wise Split View of People Staying:")
    for age_group in sorted(v_report['age_view'].keys()):
        print(f"\n--- {age_group} ---")
        group_data = v_report['age_view'][age_group]
        total_in_group = len(group_data.get('M', [])) + len(group_data.get('F', [])) + len(
            group_data.get('Unknown', []))
        if total_in_group == 0:
            print("  No one in this group is staying.")
            continue

        if group_data['M']:
            print(f"  Male ({len(group_data['M'])}):")
            for p in group_data['M']: print(f"    - {p['name']} (Age: {p['age']}, Contact: {p['contact']})")
        if group_data['F']:
            print(f"  Female ({len(group_data['F'])}):")
            for p in group_data['F']: print(f"    - {p['name']} (Age: {p['age']}, Contact: {p['contact']})")
        if group_data['Unknown']:
            print(f"  Unknown Gender ({len(group_data['Unknown'])}):")
            for p in group_data['Unknown']: print(f"    - {p['name']} (Age: {p['age']}, Contact: {p['contact']})")

    # --- REPORT 3: DETAILED MEAL PLAN ---
    print("\n" + "=" * 80)
    print(f"REPORT 3: MEAL & BEVERAGE PLAN ({', '.join(DATES_OF_INTEREST)})")
    print("=" * 80)
    for date, plan in reports['meal_plan'].items():
        print(f"\n--- Date: {datetime.strptime(date, '%Y-%m-%d').strftime('%A, %d %B %Y')} ---")
        print("  Morning Beverages:")
        print(f"    - Tea: {plan['morning_tea']}")
        print(
            f"    - Coffee (Total): {plan['morning_coffee']} (With Sugar: {plan['morning_coffee_sugar']}, No Sugar: {plan['morning_coffee_nosugar']})")
        print("  Meals:")
        print(f"    - Breakfast: {plan['breakfast']}")
        print(f"    - Lunch: {plan['lunch']}")
        print(f"    - Dinner: {plan['dinner']}")
        print("  High Tea Beverages:")
        print(f"    - Tea (Total): {plan['high_tea']} (No Sugar: {plan['high_tea_nosugar']})")
        print(f"    - Coffee (Total): {plan['high_coffee']} (No Sugar: {plan['high_coffee_nosugar']})")

    # --- REPORT 4: COT REQUIREMENTS ---
    print("\n" + "=" * 80)
    print("REPORT 4: DAILY COT REQUIREMENTS")
    print("=" * 80)
    c_report = reports['cot_needs']
    if not c_report:
        print("\nNo cots required on any day.")
    else:
        for date in sorted(c_report.keys()):
            daily_cot_needs = c_report[date]
            print(f"\n--- Date: {datetime.strptime(date, '%Y-%m-%d').strftime('%A, %d %B %Y')} ---")
            print(f"  Total Cots Needed: {daily_cot_needs['total']}")
            print(f"    - Women: {daily_cot_needs['women']}")
            print(f"    - Men: {daily_cot_needs['men']}")
            print("  List of People:")
            for person in daily_cot_needs['list']:
                print(f"    - Name: {person['name']}, Contact: {person['contact']}")

    # --- REPORT 5: TRAVEL ASSISTANCE ---
    print("\n" + "=" * 80)
    print("REPORT 5: TRAVEL ASSISTANCE LIST")
    print("=" * 80)
    a_report = reports['travel_assistance']
    print(f"\nTotal People Needing Assistance: {a_report['total']}")
    if a_report['total'] > 0:
        print("Gender-wise Headcount:")
        for gender, count in a_report['gender_counts'].items():
            print(f"  - {gender}: {count}")
        print("\nList of People Needing Assistance:")
        for person in a_report['list']:
            print(f"  - Name: {person['name']}, Age: {person['age']}, Contact: {person['contact']}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print(f"Generating reports from DynamoDB table: '{TABLE_NAME}'...")
    # This is the main function call that kicks everything off.
    final_reports = process_registrations(TABLE_NAME)
    print_final_reports(final_reports)

