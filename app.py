
import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
from fuzzywuzzy import process
import json
import os
import datetime
import openrouteservice
from openrouteservice import convert
# Consumer selection logging
LOG_FILE = "consumer_log.json"

def log_consumer_selection(food, origin, destination):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "food": food,
        "origin": origin,
        "destination": destination
    }
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []
    data.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)
def get_directions(origin_coord, dest_coord, ors_api_key):
    client = openrouteservice.Client(key=ors_api_key)
    coords = ( (origin_coord[1], origin_coord[0]), (dest_coord[1], dest_coord[0]) )  # lon, lat
    try:
        route = client.directions(coords, profile='driving-car', format='geojson')
        summary = route['features'][0]['properties']['summary']
        steps = []
        # decode steps if available
        segments = route['features'][0]['properties'].get('segments', [])
        for seg in segments:
            for step in seg.get('steps', []):
                steps.append(step.get('instruction'))
        geometry = route['features'][0]['geometry']
        return {
            "distance_m": summary.get("distance"),
            "duration_s": summary.get("duration"),
            "steps": steps,
            "geometry": geometry
        }
    except Exception as e:
        return None

DESTINATION = (13.0827, 80.2707)

PROCESS_TEMPLATES = {
    "Rice": ["Harvesting", "Cleaning", "Milling", "Packaging", "Transport"],
    "Tomato": ["Harvesting", "Grading", "Cooling", "Packaging", "Transport"],
    "Milk": ["Collection", "Pasteurization", "Packaging", "Distribution"],
}

MENTOR_FAQ = {
    "how to get fssai": "Go to fssai.gov.in, register as a food business, and apply for a license.",
    "how to find manufacturers": "Search local co-packers via IndiaMART or use the supplier finder section.",
    "how to reduce waste": "Combine redundant steps and switch to reusable packaging.",
    "what schemes are available": "Look into PMFME, StartupTN, and state agriculture subsidies."
}

@st.cache_data
def load_food_data():
    return pd.read_csv("mealsense_100_foods.csv")

df = load_food_data()

st.set_page_config(page_title="MealSense", layout="wide")
st.title("🍽️ MealSense – Food Trace & Startup Plan")
st.sidebar.title("Navigation")
mode = st.sidebar.radio("View as:", ["Consumer", "Supplier", "Mentor Bot"])

if mode == "Consumer":
    st.subheader("🌍 Trace Your Food (Real-time Route)")
    st.info("Select a food item and define origin/destination. Route, distance, time, and emissions are calculated accurately.")

    food_choice = st.selectbox("Food item", sorted(df["Food"].unique()))

    # From / To inputs
    origin_input = st.text_input("From (e.g., Thanjavur, Tamil Nadu)", "Thanjavur, Tamil Nadu")
    dest_input = st.text_input("To (e.g., Chennai, Tamil Nadu)", "Chennai, Tamil Nadu")

    # Geocode using Nominatim as fallback (could be replaced for scale)
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="mealsense")
    origin_loc = geolocator.geocode(origin_input)
    dest_loc = geolocator.geocode(dest_input)

    if origin_loc and dest_loc:
        origin_coords = (origin_loc.latitude, origin_loc.longitude)
        dest_coords = (dest_loc.latitude, dest_loc.longitude)

        # Directions via OpenRouteService
        ORS_API_KEY = st.secrets.get("ORS_API_KEY", "")  # store your key in Streamlit secrets or define directly (not recommended)
        if not ORS_API_KEY:
            st.warning("OpenRouteService API key missing. Put it in Streamlit secrets as ORS_API_KEY.")
        route_info = None
        if ORS_API_KEY:
            route_info = get_directions(origin_coords, dest_coords, ORS_API_KEY)

        # Fallback distance if directions failed
        from geopy.distance import geodesic
        if route_info:
            distance_km = round(route_info["distance_m"] / 1000, 2)
            duration_min = round(route_info["duration_s"] / 60, 1)
        else:
            distance_km = round(geodesic(origin_coords, dest_coords).km, 2)
            duration_min = None

        # Log this selection for demand aggregation
        log_consumer_selection(food_choice, origin_input, dest_input)

        # Show details
        st.markdown(f"**Distance:** {distance_km} km")
        if duration_min:
            st.markdown(f"**Estimated Travel Time:** {duration_min} minutes")
        # Simple transport carbon: factor (e.g., 0.002 kg CO2 per km per kg)
        transport_co2 = distance_km * 0.002
        st.markdown(f"**Transport Carbon Footprint (approx):** {transport_co2:.2f} kg CO₂e")

        # Show matched food metadata
        row = df[df["Food"] == food_choice].iloc[0]
        st.markdown(f"**Origin State (template):** {row['Origin State']}")
        st.markdown(f"**Category:** {row['Category']}")
        st.markdown(f"**Estimated Cost:** ₹{row['Cost_INR_per_kg']} per kg")
        st.markdown(f"**Base Carbon Footprint:** {row['Carbon_kgCO2e_per_kg']} kg CO₂e/kg")
        st.markdown(f"**Water Use:** {row['Water_liters_per_kg']} L/kg")

        # Nutrition
        st.subheader("Nutrition (approx)")
        if pd.notna(row.get("Calories_per_100g")):
            st.write(f"Calories: {row['Calories_per_100g']}")
            st.write(f"Protein: {row['Protein_g']} g")
            st.write(f"Carbs: {row['Carbs_g']} g")
            st.write(f"Fat: {row['Fat_g']} g")

        # Directions steps
        if route_info and route_info.get("steps"):
            st.subheader("🔀 Directions")
            for step in route_info["steps"]:
                st.write(f"- {step}")

        # Map
        st.subheader("🗺️ Route Map")
        m = folium.Map(location=[(origin_coords[0]+dest_coords[0])/2, (origin_coords[1]+dest_coords[1])/2], zoom_start=6)
        folium.Marker(location=origin_coords, popup=f"Origin: {origin_input}", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(location=dest_coords, popup=f"Destination: {dest_input}", icon=folium.Icon(color="red")).add_to(m)
        if route_info and route_info.get("geometry"):
            folium.GeoJson(route_info["geometry"], name="route").add_to(m)
        else:
            folium.PolyLine([origin_coords, dest_coords], color="blue", weight=2.5).add_to(m)
        st_folium(m, width=700, height=450)
    else:
        st.warning("Could not geocode origin or destination. Try more specific place names.")


elif mode == "Supplier":
    st.subheader("🏭 Startup Assistance Plan")
    st.info("Upload a photo or enter a food name. We'll identify the item, show process steps, and give dashboard insights.")

    # Image upload + fallback name input
    uploaded_image = st.file_uploader("Upload food photo (optional)", type=["jpg", "png", "jpeg"])
    uploaded_name = st.text_input("Or enter food name (e.g., Rice, Tomato, Milk)")

    # Determine query string: prefer model in future, for now use text
    query_name = uploaded_name.strip()
    if uploaded_image and not query_name:
        st.markdown("🖼️ Image received (auto-detection placeholder). Please type name if identification is ambiguous.")
        # placeholder: in future run classifier here to set query_name
        query_name = st.text_input("If auto-detection failed, type the food name here", "")

    best_match = None
    score = 0
    matched_row = {}
    process_steps = ["Step 1", "Step 2", "Step 3"]

    if query_name:
        choices = df["Food"].unique().tolist()
        best_match, score = process.extractOne(query_name, choices) if choices else (query_name, 0)
        st.markdown(f"**Detected as:** {best_match} (confidence {score}%)")

        if best_match in df["Food"].values:
            matched_row = df[df["Food"] == best_match].iloc[0]
            category = best_match.split()[0]
            process_steps = PROCESS_TEMPLATES.get(category, ["Step 1", "Step 2", "Step 3"])
        else:
            matched_row = {}

        # Suggested manufacturing process
        st.markdown("#### Suggested Manufacturing Process:")
        for i, step in enumerate(process_steps, 1):
            st.write(f"{i}. {step}")

        if len(process_steps) > 4:
            st.warning("⚠️ Process seems long; consider combining adjacent steps.")
        else:
            st.success("✅ Process is leaner. Good start!")

        # Startup plan summary
        st.markdown("#### Quick Startup Plan Report")
        st.write(f"📦 Product: {best_match}")
        st.write(f"🏷️ Category: {matched_row.get('Category', '')}")
        st.write(f"💰 Estimated Base Cost: ₹{matched_row.get('Cost_INR_per_kg', '')} per kg")
        st.write(f"🌱 Carbon Footprint: {matched_row.get('Carbon_kgCO2e_per_kg', '')} kg CO₂e/kg")
        st.write(f"🔄 Suggested Process: {', '.join(process_steps)}")

    # ---------------------------
    # Supplier Dashboard Section
    # ---------------------------
    st.markdown("---")
    st.subheader("📊 Supplier Dashboard")

    # Example supplier location (could be made dynamic later)
    supplier_location = (11.0168, 76.9558)  # Coimbatore

    # Mock consumer demand centers (will come from real logged data later)
    demand_centers = [
        {"city": "Chennai", "coords": (13.0827, 80.2707), "demand": 120},
        {"city": "Madurai", "coords": (9.9252, 78.1198), "demand": 80},
    ]

    # Example metrics (replace with real aggregations when available)
    st.metric("Total Consumer Requests (this week)", 230)
    st.metric("Avg Sustainability Score of your products", "72/100")
    st.metric("Top Inefficiency", "Packaging double-step", delta="Improve by 15%")

    # Demand Map
    st.subheader("📍 Demand Map")
    m2 = folium.Map(location=supplier_location, zoom_start=6)
    folium.Marker(location=supplier_location, popup="Your Facility", icon=folium.Icon(color="blue")).add_to(m2)
    for center in demand_centers:
        folium.CircleMarker(
            location=center["coords"],
            radius=5 + center["demand"] / 30,
            popup=f"{center['city']} demand: {center['demand']}",
            color="orange",
            fill=True,
            fill_opacity=0.6
        ).add_to(m2)
        folium.PolyLine([supplier_location, center["coords"]], color="purple", dash_array="5").add_to(m2)
    st_folium(m2, width=700, height=450)

    # Cross-View: link with consumer trace
    st.markdown("---")
    st.subheader("🔗 Cross-View: Consumer & Supplier for Same Food")
    link_food_choice = st.selectbox("Select a food to compare views", sorted(df["Food"].unique()))

    # Consumer snapshot for that food
    consumer_row = df[df["Food"] == link_food_choice].iloc[0]
    st.markdown("### Consumer Perspective")
    st.write(f"🌍 Origin State: {consumer_row.get('Origin State', '')}")
    # If you have stored user-selected destination you can show it; fallback distance
    st.write(f"📏 Distance to Chennai (template): {consumer_row.get('Distance_km', 'N/A')} km")
    sustainability_score = round(100 - (consumer_row.get('Carbon_kgCO2e_per_kg', 0) * 10), 1)
    st.write(f"♻️ Sustainability Score: {sustainability_score}/100")

    st.markdown("### Supplier Perspective")
    st.write("Suggested Process Steps:", ", ".join(PROCESS_TEMPLATES.get(link_food_choice.split()[0], ['Step 1', 'Step 2'])))

elif mode == "Mentor Bot":
    st.subheader("🧠 Food Startup Mentor Bot")
    query = st.text_input("Ask a question (e.g., 'how to reduce waste'):")
    if query:
        key = query.lower().strip()
        answer = None
        for faq_k, faq_v in MENTOR_FAQ.items():
            if faq_k in key:
                answer = faq_v
                break
        if answer:
            st.success(answer)
        else:
            st.info("No direct answer found. Try simpler phrases.")
