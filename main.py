from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from boto3.dynamodb.types import TypeDeserializer
import os
from pydantic import BaseModel
import boto3
from fastapi import HTTPException
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="my-images"), name="static")
# CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

deserializer = TypeDeserializer()

# Mount static files (for your JS file)
app.mount("/js", StaticFiles(directory="static/js"), name="js")

from typing import List, Dict, Optional


# Pydantic Models for Registration Data
class MainRegistrant(BaseModel):
    mobile: str
    firstName: str
    lastName: str
    ref1: str
    ref2: str


class MorningTeaCoffee(BaseModel):
    preference: str
    sugar: str


class MealPreferenceDay(BaseModel):
    breakfast: bool
    lunch: bool
    highTea: bool
    dinner: bool
    teaCoffeePreference: str
    teaCoffeeSugar: str
    packedFood: bool


class MemberDetails(BaseModel):
    firstName: str
    lastName: str
    mobile: str
    age: int  # Changed from str to int
    gender: str
    arrivalDate: str
    arrivalTime: str
    departureDate: str
    departureTime: str
    attendingDates: List[str]
    morningTeaCoffee: MorningTeaCoffee
    mealPreferences: Dict[str, MealPreferenceDay]
    stayAtHall: bool
    cotRequired: bool
    difficultyClimbingStairs: bool
    modeOfTransport: str
    cityOfOrigin: str
    localAssistance: Optional[str] = ""
    recordingsNeeded: Optional[str] = ""
    specialRequests: Optional[str] = ""


class TravelDetails(BaseModel):
    members: List[MemberDetails]


class RegistrationData(BaseModel):
    mainRegistrant: MainRegistrant
    travelDetails: TravelDetails
    registrationId: str


# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')  # Replace with your desired region
table_name = 'users'
table = dynamodb.Table(table_name)
shop_table_name = 'gurukul-shop'

# Create table if it doesn't exist (optional, can be done manually)
try:
    table.load()
except Exception as e:
    # A common exception here is ResourceNotFoundException
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'registrationId',  # Changed from username
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'registrationId',  # Changed from username
                    'AttributeType': 'S'  # String type for registrationId
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        table.wait_until_exists()
    else:
        # Handle other exceptions as needed
        raise


@app.get("/chat", response_class=HTMLResponse)
async def get_chat_page():
    with open("static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.post("/chat")
async def chat_dummy():
    return {"reply": "Thanks for your message! (This is a dummy response)"}


@app.get("/", response_class=HTMLResponse)
async def greet_page():
    with open("static/home-page.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(html_content)


@app.get("/location", response_class=HTMLResponse)
async def return_location_page():
    with open("static/location.html", "r") as f:
        read_location_page = f.read()
    return HTMLResponse(read_location_page)


@app.get("/contact-us", response_class=HTMLResponse)
async def return_contact_page():
    with open("static/contact-us.html", "r") as f:
        read_contact_page = f.read()
    return HTMLResponse(read_contact_page)


@app.post("/register")
async def register_user(registration_data: RegistrationData):
    try:
        # Convert Pydantic model to dict for DynamoDB
        # DynamoDB cannot store empty strings for optional fields if they are part of an index or key.
        # However, for general attributes, empty strings are usually fine.
        # For simplicity here, we're directly converting.
        # Consider adding a utility to clean empty strings if issues arise or for best practice.
        item_data = registration_data.dict()

        # The primary key 'registrationId' is already part of item_data
        table.put_item(Item=item_data)
        return {"message": "User registered successfully", "registrationId": registration_data.registrationId}
    except Exception as e:
        # Log the exception for debugging
        print(f"Error during registration: {e}")
        # Return a more specific error response if possible
        # For now, returning a generic error with the exception message
        return {"error": str(e), "details": "Failed to register user data in DynamoDB."}


@app.get("/get-registrations", response_class=HTMLResponse)
async def return_view_registration_page():
    with open("static/view-registration.html", "r") as f:
        read_contact_page = f.read()
    return HTMLResponse(read_contact_page)


# helper for dynamoDB fetch 

def clean_dynamo_item(item):
    def _deserialize(value):
        try:
            if isinstance(value, dict) and len(value) == 1:
                return deserializer.deserialize(value)
            elif isinstance(value, dict):
                return {k: _deserialize(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_deserialize(v) for v in value]
            else:
                return value
        except Exception as e:
            print(f"Deserialization error: {e}")
            return value  # fallback: return raw

    return _deserialize(item)


# handle registration post req

@app.get("/get-registration/{registration_id}")
async def get_registration_details(registration_id: str):
    try:
        response = table.get_item(
            Key={
                'registrationId': registration_id
            }
        )
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Registration not found")

        print("✅ Raw DynamoDB item:")
        print(response['Item'])

        clean_item = clean_dynamo_item(response['Item'])
        return clean_item

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@app.delete("/delete-registration/{registration_id}")
async def delete_registration(registration_id: str):
    try:
        response = table.delete_item(
            Key={"registrationId": registration_id},
            ReturnValues="ALL_OLD"
        )
        if 'Attributes' not in response:
            raise HTTPException(status_code=404, detail="Registration not found to delete.")
        return {"message": f"Registration ID {registration_id} successfully deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


# writing the shop code 
@app.get("/shop", response_class=HTMLResponse)
async def return_shop_page():
    with open("static/shop.html", "r") as f:
        read_shop = f.read()
    return HTMLResponse(read_shop)


from fastapi import HTTPException
from pydantic import BaseModel
from typing import List
import boto3
import uuid


# Define your Pydantic models
class BookItem(BaseModel):
    name: str
    quantity: int
    price_per_item: int


class PurchaseData(BaseModel):
    name: str
    phone: str
    books: List[BookItem]
    total_price: int
    timestamp: str


@app.post("/submit-purchase")
async def submit_purchase(purchase: PurchaseData):
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')

        # Get or create the table with phone as partition key
        try:
            shop_table = dynamodb.Table('gurukul-shop')
            shop_table.load()
        except Exception as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                shop_table = dynamodb.create_table(
                    TableName='gurukul-shop',
                    KeySchema=[
                        {'AttributeName': 'phone', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'phone', 'AttributeType': 'S'}
                    ],
                    ProvisionedThroughput={
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                )
                shop_table.wait_until_exists()
            else:
                raise

        purchase_id = str(uuid.uuid4())

        shop_table.put_item(
            Item={
                "phone": purchase.phone,  # ✅ phone as PK
                "purchase_id": purchase_id,
                "name": purchase.name,
                "books": [book.dict() for book in purchase.books],
                "total_price": purchase.total_price,
                "timestamp": purchase.timestamp
            }
        )

        return {
            "message": "Purchase stored successfully ✅",
            "purchase_id": purchase_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Failed to store purchase: {str(e)}")


# utsav timetable
@app.get("/timetable", response_class=HTMLResponse)
async def return_utsav_timetable():
    with open("static/timetable.html", "r") as f:
        read_contact_page = f.read()
    return HTMLResponse(read_contact_page)

# doing admin analysis here
simulated_dynamodb_data = [
    {
        'registrationId': {
            "S": "REG-2025-27CD93DE"
        },
        'mainRegistrant': {
            "M": {
                "firstName": {
                    "S": "Daku"
                },
                "lastName": {
                    "S": "Mangalsingh"
                },
                "mobile": {
                    "S": "+919834725816"
                },
                "ref1": {
                    "S": "+911234567899"
                },
                "ref2": {
                    "S": "+911234567899"
                }
            }
        },
        'travelDetails': {
            "M": {
                "members": {
                    "L": [
                        {
                            "M": {
                                "age": {
                                    "N": "23"
                                },
                                "arrivalDate": {
                                    "S": "08|07|2025"
                                },
                                "arrivalTime": {
                                    "S": "01:01"
                                },
                                "attendingDates": {
                                    "L": [
                                        {
                                            "S": "2025-07-08"
                                        },
                                        {
                                            "S": "2025-07-09"
                                        },
                                        {
                                            "S": "2025-07-10"
                                        },
                                        {
                                            "S": "2025-07-11"
                                        }
                                    ]
                                },
                                "cityOfOrigin": {
                                    "S": "dholakpur"
                                },
                                "cotRequired": {
                                    "BOOL": True
                                },
                                "departureDate": {
                                    "S": "11|07|2025"
                                },
                                "departureTime": {
                                    "S": "13:01"
                                },
                                "difficultyClimbingStairs": {
                                    "BOOL": True
                                },
                                "firstName": {
                                    "S": "Daku"
                                },
                                "gender": {
                                    "S": "M"
                                },
                                "lastName": {
                                    "S": "Mangalsingh"
                                },
                                "localAssistance": {
                                    "S": "Suhas Joglekar"
                                },
                                "mealPreferences": {
                                    "M": {
                                        "2025-07-08": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": False
                                                },
                                                "dinner": {
                                                    "BOOL": True
                                                },
                                                "highTea": {
                                                    "BOOL": True
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "coffee"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        },
                                        "2025-07-09": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": True
                                                },
                                                "dinner": {
                                                    "BOOL": True
                                                },
                                                "highTea": {
                                                    "BOOL": True
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "coffee"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        },
                                        "2025-07-10": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": True
                                                },
                                                "dinner": {
                                                    "BOOL": True
                                                },
                                                "highTea": {
                                                    "BOOL": True
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "coffee"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        },
                                        "2025-07-11": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": True
                                                },
                                                "dinner": {
                                                    "BOOL": True
                                                },
                                                "highTea": {
                                                    "BOOL": True
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "coffee"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        }
                                    }
                                },
                                "mobile": {
                                    "S": "+1919834725816"
                                },
                                "modeOfTransport": {
                                    "S": "Car"
                                },
                                "morningTeaCoffee": {
                                    "M": {
                                        "preference": {
                                            "S": "coffee"
                                        },
                                        "sugar": {
                                            "S": "sugar"
                                        }
                                    }
                                },
                                "recordingsNeeded": {
                                    "S": "gurupoojan main"
                                },
                                "specialRequests": {
                                    "S": "hot water"
                                },
                                "stayAtHall": {
                                    "BOOL": True
                                }
                            }
                        },
                        {
                            "M": {
                                "age": {
                                    "N": "45"
                                },
                                "arrivalDate": {
                                    "S": "08|07|2025"
                                },
                                "arrivalTime": {
                                    "S": "01:01"
                                },
                                "attendingDates": {
                                    "L": [
                                        {
                                            "S": "2025-07-08"
                                        },
                                        {
                                            "S": "2025-07-09"
                                        }
                                    ]
                                },
                                "cityOfOrigin": {
                                    "S": "dholakpur"
                                },
                                "cotRequired": {
                                    "BOOL": False
                                },
                                "departureDate": {
                                    "S": "09|07|2025"
                                },
                                "departureTime": {
                                    "S": "01:01"
                                },
                                "difficultyClimbingStairs": {
                                    "BOOL": True
                                },
                                "firstName": {
                                    "S": "Chota"
                                },
                                "gender": {
                                    "S": "M"
                                },
                                "lastName": {
                                    "S": "Bheem"
                                },
                                "localAssistance": {
                                    "S": "Suhas Joglekar"
                                },
                                "mealPreferences": {
                                    "M": {
                                        "2025-07-08": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": False
                                                },
                                                "dinner": {
                                                    "BOOL": False
                                                },
                                                "highTea": {
                                                    "BOOL": False
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "none"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        },
                                        "2025-07-09": {
                                            "M": {
                                                "breakfast": {
                                                    "BOOL": True
                                                },
                                                "dinner": {
                                                    "BOOL": True
                                                },
                                                "highTea": {
                                                    "BOOL": True
                                                },
                                                "lunch": {
                                                    "BOOL": True
                                                },
                                                "packedFood": {
                                                    "BOOL": False
                                                },
                                                "teaCoffeePreference": {
                                                    "S": "coffee"
                                                },
                                                "teaCoffeeSugar": {
                                                    "S": "sugar"
                                                }
                                            }
                                        }
                                    }
                                },
                                "mobile": {
                                    "S": "+1919834725816"
                                },
                                "modeOfTransport": {
                                    "S": "Car"
                                },
                                "morningTeaCoffee": {
                                    "M": {
                                        "preference": {
                                            "S": "none"
                                        },
                                        "sugar": {
                                            "S": "sugar"
                                        }
                                    }
                                },
                                "recordingsNeeded": {
                                    "S": ""
                                },
                                "specialRequests": {
                                    "S": ""
                                },
                                "stayAtHall": {
                                    "BOOL": False
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
]


@app.get("/")
async def root():
    return {"message": "Welcome to the Registration Analysis API. Access /dashboard to view the admin dashboard."}


# This endpoint will serve the HTML dashboard page
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_html():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Event Dashboard</title>
        <style>
            body { font-family: sans-serif; background: #f0f0f0; padding: 20px; }
            .section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h2 { color: #333; }
            ul { padding-left: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
            th { background-color: #eee; }
        </style>
    </head>
    <body>
        <h1>Event Summary Dashboard</h1>
        <div id="dashboard"></div>

        <script>
            async function loadDashboard() {
                const res = await fetch('http://127.0.0.1:8000/dashboard-data'); // This URL needs to fetch JSON data
                const data = await res.json();

                // Note: The HTML structure here expects the previous summary format.
                // To display the new detailed participant list, this HTML/JS would need to be updated.
                // For demonstration, we'll just show the raw data if it's not in the expected summary format.
                if (Array.isArray(data)) {
                    let html = '<div class="section"><h2>All Participants Raw Data</h2>';
                    html += '<table border="1"><thead><tr><th>Name</th><th>Gender</th><th>Mobile</th><th>Age</th><th>Stay at Hall</th><th>Cot Needed</th><th>Stairs Difficulty</th><th>Local Assistance</th><th>Recordings</th><th>Special Requests</th><th>Morning Tea/Coffee</th><th>Attending Dates</th><th>Meal Preferences (Details)</th></tr></thead><tbody>';
                    data.forEach(p => {
                        html += `<tr>
                                    <td>${p.firstName} ${p.lastName}</td>
                                    <td>${p.gender}</td>
                                    <td>${p.mobile}</td>
                                    <td>${p.age}</td>
                                    <td>${p.stayAtHall ? 'Yes' : 'No'}</td>
                                    <td>${p.cotRequired ? 'Yes' : 'No'}</td>
                                    <td>${p.difficultyClimbingStairs ? 'Yes' : 'No'}</td>
                                    <td>${p.localAssistance || 'N/A'}</td>
                                    <td>${p.recordingsNeeded || 'N/A'}</td>
                                    <td>${p.specialRequests || 'N/A'}</td>
                                    <td>${p.morningTeaCoffee.preference} (${p.morningTeaCoffee.sugar})</td>
                                    <td>${p.attendingDates.join(', ')}</td>
                                    <td>${JSON.stringify(p.mealPreferences)}</td>
                                </tr>`;
                    });
                    html += '</tbody></table></div>';
                    document.getElementById("dashboard").innerHTML = html;

                } else {
                    // Fallback to previous summary display if data format is old
                    const html = `
                        <div class="section">
                            <h2>Total Participants</h2>
                            <p>Total: ${data.total_participants}</p>
                            <ul>${Object.entries(data.gender_count).map(([g, c]) => `<li>${g}: ${c}</li>`).join("")}</ul>
                        </div>

                        <div class="section">
                            <h2>Staying at Venue</h2>
                            <p>Total: ${data.staying_count}</p>
                            <ul>${Object.entries(data.staying_gender).map(([g, c]) => `<li>${g}: ${c}</li>`).join("")}</ul>
                        </div>

                        <div class="section">
                            <h2>Meal Summary</h2>
                            ${Object.entries(data.meal_summary).map(([date, meals]) => `
                                <h4>${date}</h4>
                                <ul>${Object.entries(meals).map(([meal, count]) => `<li>${meal}: ${count}</li>`).join("")}</ul>
                            `).join("")}
                        </div>

                        <div class="section">
                            <h2>Tea/Coffee Preferences</h2>
                            <ul>${Object.entries(data.tea_coffee_summary).map(([drink, sugars]) =>
                                `<li>${drink}:<ul>${Object.entries(sugars).map(([sugar, count]) => `<li>${sugar}: ${count}</li>`).join("")}</ul></li>`
                            ).join("")}</ul>
                        </div>

                        <div class="section">
                            <h2>Need Assistance</h2>
                            <p>Total: ${data.assistance_needed.count}</p>
                            <ul>${Object.entries(data.assistance_needed.by_gender).map(([g, c]) => `<li>${g}: ${c}</li>`).join("")}</ul>
                            <table><tr><th>Name</th><th>Gender</th><th>Phone</th></tr>
                                ${data.assistance_needed.list.map(p => `<tr><td>${p.name}</td><td>${p.gender}</td><td>${p.phone}</td></tr>`).join("")}
                            </table>
                        </div>

                        <div class="section">
                            <h2>Need Cot</h2>
                            <p>Total: ${data.cot_needed.count}</p>
                            <ul>${Object.entries(data.cot_needed.by_gender).map(([g, c]) => `<li>${g}: ${c}</li>`).join("")}</ul>
                            <ul>${data.cot_needed.list.map(p => `<li>${p.name} (${p.gender})</li>`).join("")}</ul>
                        </div>
                    `;
                    document.getElementById("dashboard").innerHTML = html;
                }
            }

            loadDashboard();
        </script>
    </body>
    </html>
    """


@app.get("/dashboard-data")  # This endpoint will now return JSON data for the dashboard
def get_all_data():
    # Use the simulated data. It is now in DynamoDB JSON format.
    items_dynamodb_json = simulated_dynamodb_data

    # We will now return a list of dictionaries, where each dictionary represents a participant
    # with all extracted details, arranged in a columnar fashion.
    all_participants_detailed = []

    for item_raw in items_dynamodb_json:
        travel_details_map = item_raw.get("travelDetails", {}).get("M", {})
        members_list_raw = travel_details_map.get("members", {}).get("L", [])

        for member_item_raw in members_list_raw:
            member_data = member_item_raw.get("M", {})

            # Extract scalar values
            first_name = member_data.get("firstName", {}).get("S", "")
            last_name = member_data.get("lastName", {}).get("S", "")
            full_name = f"{first_name} {last_name}"
            gender = member_data.get("gender", {}).get("S", "Unknown")
            age = int(member_data.get("age", {}).get("N", "0"))  # Convert age to integer
            mobile = member_data.get("mobile", {}).get("S", "N/A")

            mode_of_transport = member_data.get("modeOfTransport", {}).get("S", "N/A")
            city_of_origin = member_data.get("cityOfOrigin", {}).get("S", "N/A")
            arrival_date = member_data.get("arrivalDate", {}).get("S", "N/A")
            arrival_time = member_data.get("arrivalTime", {}).get("S", "N/A")
            departure_date = member_data.get("departureDate", {}).get("S", "N/A")
            departure_time = member_data.get("departureTime", {}).get("S", "N/A")

            # Extract list of attending dates
            attending_dates_raw = member_data.get("attendingDates", {}).get("L", [])
            attending_dates = [d.get("S") for d in attending_dates_raw if d.get("S")]

            stay_at_hall = member_data.get("stayAtHall", {}).get("BOOL", False)
            cot_required = member_data.get("cotRequired", {}).get("BOOL", False)
            difficulty_climbing_stairs = member_data.get("difficultyClimbingStairs", {}).get("BOOL", False)

            local_assistance = member_data.get("localAssistance", {}).get("S", "None")
            recordings_needed = member_data.get("recordingsNeeded", {}).get("S", "None")
            special_requests = member_data.get("specialRequests", {}).get("S", "None")

            # Extract morningTeaCoffee preference
            morning_tea_coffee_raw = member_data.get("morningTeaCoffee", {}).get("M", {})
            morning_tea_coffee_pref = morning_tea_coffee_raw.get("preference", {}).get("S", "none")
            morning_tea_coffee_sugar = morning_tea_coffee_raw.get("sugar", {}).get("S", "sugar")

            # Extract meal preferences per day
            meal_preferences_raw = member_data.get("mealPreferences", {}).get("M", {})
            meal_preferences_parsed = {}
            for date_str, meals_data_raw in meal_preferences_raw.items():
                meals = meals_data_raw.get("M", {})
                daily_prefs = {
                    "breakfast": meals.get("breakfast", {}).get("BOOL", False),
                    "lunch": meals.get("lunch", {}).get("BOOL", False),
                    "highTea": meals.get("highTea", {}).get("BOOL", False),
                    "dinner": meals.get("dinner", {}).get("BOOL", False),
                    "packedFood": meals.get("packedFood", {}).get("BOOL", False),
                    "teaCoffeePreference": meals.get("teaCoffeePreference", {}).get("S", "none"),
                    "teaCoffeeSugar": meals.get("teaCoffeeSugar", {}).get("S", "sugar"),
                }
                meal_preferences_parsed[date_str] = daily_prefs

            all_participants_detailed.append({
                "firstName": first_name,
                "lastName": last_name,
                "fullName": full_name,  # Added for convenience
                "gender": gender,
                "age": age,
                "mobile": mobile,
                "modeOfTransport": mode_of_transport,
                "cityOfOrigin": city_of_origin,
                "arrivalDate": arrival_date,
                "arrivalTime": arrival_time,
                "departureDate": departure_date,
                "departureTime": departure_time,
                "attendingDates": attending_dates,
                "stayAtHall": stay_at_hall,
                "cotRequired": cot_required,
                "difficultyClimbingStairs": difficulty_climbing_stairs,
                "localAssistance": local_assistance,
                "recordingsNeeded": recordings_needed,
                "specialRequests": special_requests,
                "morningTeaCoffee": {
                    "preference": morning_tea_coffee_pref,
                    "sugar": morning_tea_coffee_sugar
                },
                "mealPreferences": meal_preferences_parsed  # Store the parsed dictionary
            })

    return all_participants_detailed
