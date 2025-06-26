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