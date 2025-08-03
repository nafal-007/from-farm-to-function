
import streamlit as st
import pandas as pd
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
from fuzzywuzzy import process

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
    st.subheader("🌍 Trace Your Food")
    food_choice = st.selectbox("Food item", sorted(df["Food"].unique()))
    row = df[df["Food"] == food_choice].iloc[0]
    origin_coords = (row.get("Origin Lat", 13.0827), row.get("Origin Lon", 80.2707))
    distance_km = round(geodesic(origin_coords, DESTINATION).km, 2)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"**Origin State:** {row.get('Origin State', '')}")
        st.markdown(f"**Category:** {row.get('Category', '')}")
        st.markdown(f"**Distance to Chennai:** {distance_km} km")
        st.markdown(f"**Estimated Cost:** ₹{row.get('Cost_INR_per_kg', '')} per kg")
        st.markdown(f"**Carbon Footprint:** {row.get('Carbon_kgCO2e_per_kg', '')} kg CO₂e/kg")
        st.markdown(f"**Water Use:** {row.get('Water_liters_per_kg', '')} L/kg")
    with col2:
        st.subheader("Nutrition (approx)")
        if pd.notna(row.get("Calories_per_100g")):
            st.write(f"Calories: {row.get('Calories_per_100g')}")
            st.write(f"Protein: {row.get('Protein_g')} g")
            st.write(f"Carbs: {row.get('Carbs_g')} g")
            st.write(f"Fat: {row.get('Fat_g')} g")

    st.subheader("🗺️ Route Map")
    m = folium.Map(location=[(origin_coords[0] + DESTINATION[0]) / 2, (origin_coords[1] + DESTINATION[1]) / 2], zoom_start=5)
    folium.Marker(location=origin_coords, popup=f"Origin: {row.get('Food')} ({row.get('Origin State')})", icon=folium.Icon(color='green')).add_to(m)
    folium.Marker(location=DESTINATION, popup="Chennai (Delivery)", icon=folium.Icon(color='red')).add_to(m)
    folium.PolyLine([origin_coords, DESTINATION], color='blue', weight=2.5).add_to(m)
    st_folium(m, width=700, height=450)

elif mode == "Supplier":
    st.subheader("🏭 Startup Assistance Plan")
    uploaded_name = st.text_input("Enter food name (e.g., Rice, Tomato, Milk)")

    if uploaded_name:
        choices = df["Food"].unique().tolist()
        best_match, score = process.extractOne(uploaded_name, choices) if choices else (uploaded_name, 0)
        st.markdown(f"**Detected as:** {best_match} (confidence {score}%)")

        matched_row = df[df["Food"] == best_match].iloc[0] if best_match in df["Food"].values else {}
        category = best_match.split()[0]
        process_steps = PROCESS_TEMPLATES.get(category, ["Step 1", "Step 2", "Step 3"])

        st.markdown("#### Suggested Manufacturing Process:")
        for i, step in enumerate(process_steps, 1):
            st.write(f"{i}. {step}")

        if len(process_steps) > 4:
            st.warning("⚠️ Process seems long; consider combining adjacent steps.")
        else:
            st.success("✅ Process is leaner. Good start!")

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

    # Example: Supplier's fixed location
    supplier_location = (11.0168, 76.9558)  # Example: Coimbatore

    # Example demand centers (mock data until real logs from consumer side)
    demand_centers = [
        {"city": "Chennai", "coords": (13.0827, 80.2707), "demand": 120},
        {"city": "Madurai", "coords": (9.9252, 78.1198), "demand": 80},
    ]

    # Metrics
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

    # Cross-View Link to Consumer Side
    st.markdown("---")
    st.subheader("🔗 Cross-View: Consumer & Supplier for Same Food")
    link_food_choice = st.selectbox("Select a food to compare views", sorted(df["Food"].unique()))

    consumer_row = df[df["Food"] == link_food_choice].iloc[0]
    st.markdown("### Consumer Perspective")
    st.write(f"🌍 Origin State: {consumer_row['Origin State']}")
    st.write(f"📏 Distance to Chennai: {consumer_row['Distance_km']} km")
    st.write(f"♻️ Sustainability Score: {round(100 - (consumer_row['Carbon_kgCO2e_per_kg'] * 10), 1)}/100")

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
