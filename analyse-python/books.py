import boto3
from boto3.dynamodb.types import TypeDeserializer
from collections import defaultdict
from decimal import Decimal

# --- Configuration ---
# Replace 'gurukul-utsav' with your actual DynamoDB table name if it's different.
TABLE_NAME = "gurukul-shop"

# --- AWS and DynamoDB Initialization ---
# This script assumes your AWS credentials are configured in your environment
# (e.g., via `aws configure` or environment variables).
try:
    dynamodb_client = boto3.client('dynamodb')
    deserializer = TypeDeserializer()
except Exception as e:
    print(f"Error: Could not initialize Boto3. Please check your AWS credentials.")
    print(f"Details: {e}")
    exit()


def deserialize_dynamodb_item(item):
    """
    Converts a DynamoDB-formatted item into a standard Python dictionary.
    The TypeDeserializer handles the conversion of DynamoDB's data types (e.g., {'S': 'value'})
    into standard Python types.
    """
    return {k: deserializer.deserialize(v) for k, v in item.items()}


def generate_sales_report(table_name):
    """
    Scans the entire DynamoDB table, processes each purchase record,
    and returns a structured report.
    """
    all_orders = []
    book_inventory_summary = defaultdict(int)
    total_sales_value = Decimal('0.0')

    paginator = dynamodb_client.get_paginator('scan')

    try:
        # The paginator handles fetching all items from the table, even if there are millions.
        for page in paginator.paginate(TableName=table_name):
            for item in page.get('Items', []):
                # Convert the raw DynamoDB item into a usable Python dict
                order = deserialize_dynamodb_item(item)

                # Add the processed order to our list of all orders
                all_orders.append(order)

                # Update the total sales value
                total_sales_value += order.get('total_price', Decimal('0.0'))

                # Iterate through the books in this specific order to update the inventory summary
                for book in order.get('books', []):
                    book_name = book.get('name')
                    quantity = book.get('quantity', 0)
                    if book_name and quantity > 0:
                        book_inventory_summary[book_name] += quantity

    except dynamodb_client.exceptions.ResourceNotFoundException:
        print(f"Error: The table '{table_name}' was not found.")
        print("Please ensure the table name is correct and you are in the correct AWS region.")
        return None, None, None
    except Exception as e:
        print(f"An unexpected error occurred while scanning the DynamoDB table: {e}")
        return None, None, None

    return all_orders, book_inventory_summary, total_sales_value


def print_formatted_report(orders, summary, total_sales):
    """
    Takes the processed data and prints it in a clean, human-readable format.
    """
    if orders is None:
        # This happens if there was an error during data fetching.
        return

    print("\n" + "=" * 80)
    print("                 GURUKUL UTSAV - BOOK SALES REPORT")
    print("=" * 80)

    # --- Section 1: Individual Order Details ---
    print(f"\nFound a total of {len(orders)} orders.")
    print(f"Grand Total Sales Value: ${total_sales:.2f}")
    print("\n--- Individual Order Details ---")

    for i, order in enumerate(orders, 1):
        customer_name = order.get('name', 'N/A')
        customer_phone = order.get('phone', 'N/A')
        order_total = order.get('total_price', Decimal('0.0'))

        print(f"\n{i}. Order for: {customer_name} (Phone: {customer_phone})")
        print("-" * 40)

        for book in order.get('books', []):
            name = book.get('name')
            qty = book.get('quantity')
            price = book.get('price_per_item')
            subtotal = qty * price
            print(f"   - Book: {name}")
            print(f"     Quantity: {qty} @ ${price:.2f} each | Subtotal: ${subtotal:.2f}")

        print("-" * 40)
        print(f"   Total for this order: ${order_total:.2f}")

    # --- Section 2: Distributor's Inventory Summary ---
    print("\n\n" + "=" * 80)
    print("         DISTRIBUTOR INVENTORY - TOTAL BOOKS TO BRING")
    print("=" * 80)

    if not summary:
        print("\nNo books have been ordered yet.")
    else:
        # Sort the dictionary by book name for a clean, alphabetized list
        sorted_summary = sorted(summary.items())
        print(f"\n{'Book Title':<40} | {'Total Quantity Needed':>25}")
        print(f"{'-' * 40} | {'-' * 25}")
        for book_name, total_quantity in sorted_summary:
            print(f"{book_name:<40} | {total_quantity:>25}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # This is the main execution block.
    # It calls the function to fetch data and then the function to print it.
    print(f"Fetching sales data from DynamoDB table: '{TABLE_NAME}'...")

    orders_data, inventory_summary, total_value = generate_sales_report(TABLE_NAME)

    print_formatted_report(orders_data, inventory_summary, total_value)

