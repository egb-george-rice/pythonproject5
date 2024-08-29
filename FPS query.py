import requests
import tkinter as tk
from tkinter import messagebox


# Function to perform the API query
def query_trestleiq(street_line1, city, state, zip_code):
    base_url = "https://api.trestleiq.com"  # Assuming this is the base URL; replace if needed
    api_endpoint = "address/search"  # Example endpoint, adjust as per your API structure

    # Hardcoded parameters
    query_params = {
        "street_line1": street_line1,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        # Other hardcoded parameters
        "country": "US",
        "address_type": "residential"
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}"  # Assuming API key-based authentication
    }

    response = requests.get(f"{base_url}/{api_endpoint}", headers=headers, params=query_params)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text}


# Function to format the response for better readability
def format_response(response):
    if "error" in response:
        return f"Error: {response['error'].get('message', 'An error occurred')}"

    # Formatting the location details
    output = []
    output.append(f"**Location ID**: {response.get('id', 'N/A')}")
    output.append(f"**Valid**: {'Yes' if response.get('is_valid') else 'No'}")
    output.append(
        f"**Address**: {response.get('street_line_1', 'N/A')} {response.get('street_line_2', '')}, {response.get('city', 'N/A')}, {response.get('state_code', 'N/A')} {response.get('postal_code', 'N/A')} {response.get('zip4', '')}")
    output.append(f"**Country Code**: {response.get('country_code', 'N/A')}")
    output.append(f"**Is Active**: {'Yes' if response.get('is_active') else 'No'}")
    output.append(f"**Is Commercial**: {'Yes' if response.get('is_commercial') else 'No'}")
    output.append(f"**Delivery Point**: {response.get('delivery_point', 'N/A')}")
    output.append(
        f"**Latitude/Longitude**: {response.get('lat_long', {}).get('latitude', 'N/A')}, {response.get('lat_long', {}).get('longitude', 'N/A')} (Accuracy: {response.get('lat_long', {}).get('accuracy', 'N/A')})")

    # Formatting current residents
    current_residents = response.get('current_residents', [])
    if current_residents:
        output.append("\n**Current Residents**:")
        for resident in current_residents:
            output.append(f"  - **Name**: {resident.get('name', 'N/A')} ({resident.get('age_range', 'N/A')} years old)")
            output.append(f"    **Phone Number**: {resident.get('phones', [{}])[0].get('phone_number', 'N/A')}")
            output.append(f"    **Email**: {resident.get('emails', 'N/A')}")
            output.append("    **Historical Addresses**:")
            for address in resident.get('historical_addresses', []):
                output.append(
                    f"      - {address.get('street_line_1', 'N/A')} {address.get('street_line_2', '')}, {address.get('city', 'N/A')}, {address.get('state_code', 'N/A')} {address.get('postal_code', 'N/A')} {address.get('zip4', '')}")
                output.append(f"        - Active: {'Yes' if address.get('is_active') else 'No'}")
                output.append(f"        - Linked to Person Since: {address.get('link_to_person_start_date', 'N/A')}")
                output.append(f"        - Linked to Person Until: {address.get('link_to_person_end_date', 'N/A')}")
            output.append("    **Associated People**:")
            for person in resident.get('associated_people', []):
                output.append(f"      - {person.get('name', 'N/A')} (Relation: {person.get('relation', 'N/A')})")

    # Adding any warnings
    if response.get("warnings"):
        output.append(f"\n**Warnings**: {response.get('warnings')}")

    return "\n".join(output)


# Function to handle the query button click event
def perform_query():
    street_line1 = entry_street_line1.get()
    city = entry_city.get()
    state = entry_state.get()
    zip_code = entry_zip_code.get()

    # Check that all fields are filled
    if not all([street_line1, city, state, zip_code]):
        messagebox.showerror("Input Error", "All fields must be filled out.")
        return

    result = query_trestleiq(street_line1, city, state, zip_code)

    formatted_result = format_response(result)

    # Display formatted result in a message box
    messagebox.showinfo("Query Result", formatted_result)


# Create the main window
root = tk.Tk()
root.title("TrestleIQ API Query")

# API Key (Assume it's hardcoded or retrieved securely)
api_key = "3QekuoeNz38vbP6J88lGM4NmHsfQLjf38zQ0A1Tn"  # Replace with your actual API key

# Create and place labels and entry fields
tk.Label(root, text="Street Line 1").grid(row=0)
tk.Label(root, text="City").grid(row=1)
tk.Label(root, text="State").grid(row=2)
tk.Label(root, text="Zip Code").grid(row=3)

entry_street_line1 = tk.Entry(root)
entry_city = tk.Entry(root)
entry_state = tk.Entry(root)
entry_zip_code = tk.Entry(root)

entry_street_line1.grid(row=0, column=1)
entry_city.grid(row=1, column=1)
entry_state.grid(row=2, column=1)
entry_zip_code.grid(row=3, column=1)

# Create the query button
query_button = tk.Button(root, text="Query API", command=perform_query)
query_button.grid(row=4, column=1)

# Run the GUI loop
root.mainloop()
