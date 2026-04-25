import streamlit as st
import pandas as pd
import os
import json
import googlemaps
import math
import pydeck as pdk
import plotly.express as px
from datetime import datetime


# -------------------------------------------------------------------
# Configuration & Constants
# -------------------------------------------------------------------
GOOGLE_MAPS_KEY = "AIzaSyCaP5Qxqh7UP2wSFQt0u8lQg4TM5Vj6dMM"
CACHE_FILE = "geocoding_cache.json"
DATA_FILES = {
    "2024": "Supporting data-13th March 2026.xlsx - 2024.csv",
    "2025": "Supporting data-13th March 2026.xlsx - 2025.csv",
    "2026": "Supporting data(2)-13th March 2026 - 2026.csv",
    "2027": "Supporting data(2)-13th March 2026 (1)_Possible 2027.csv"
}

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def load_and_merge_data():
    all_dfs = []
    for year, filename in DATA_FILES.items():
        if os.path.exists(filename):
            temp_df = pd.read_csv(filename)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Offering 2025' in temp_df.columns:
                temp_df.rename(columns={'Offering 2025': 'Offering'}, inplace=True)
            if 'Offering 2026' in temp_df.columns:
                temp_df.rename(columns={'Offering 2026': 'Offering'}, inplace=True)
            if 'Offering 2027' in temp_df.columns:
                temp_df.rename(columns={'Offering 2027': 'Offering'}, inplace=True)
            temp_df['Academic Year'] = str(year)
            all_dfs.append(temp_df)
    if not all_dfs: return pd.DataFrame()
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Robust numeric cleaning for ALL revenue/order columns
    rev_cols = [
        'Total Order Value (Exclusive GST)', 'Total Order Value (Inclusive GST)',
        'ASSET Revenue', 'Mindspark Revenue', 'CARES Revenue',
        'ASSET Discount', 'Mindspark Discount', 'CARES Discount',
        'Teacher Training Revenue', 'Amount Received'
    ]
    for col in rev_cols:
        if col in combined_df.columns:
            # Cast everything to string first, remove commas, then to numeric
            combined_df[col] = pd.to_numeric(
                combined_df[col].astype(str).str.replace(',', '').str.strip(), 
                errors='coerce'
            ).fillna(0).astype(float)
            
    for col in ['School Name', 'City', 'Offering', 'Division', 'Zone']:
        if col in combined_df.columns:
            combined_df[col] = combined_df[col].astype(str).str.strip().replace('nan', '')
            
    if 'State' in combined_df.columns:
        combined_df['State'] = combined_df['State'].astype(str).str.strip().replace('nan', '')
        state_mapping = {
            'ap': 'Andhra Pradesh', 'andhra pradesh': 'Andhra Pradesh', 'arunachal pradesh': 'Arunachal Pradesh', 
            'assam': 'Assam', 'bihar': 'Bihar', 'chattisgarh': 'Chhattisgarh', 'chhattisgarh': 'Chhattisgarh',
            'cg': 'Chhattisgarh', 'goa': 'Goa', 'gujarat': 'Gujarat', 'gujrat': 'Gujarat',
            'gj': 'Gujarat', 'haryana': 'Haryana', 'hr': 'Haryana', 'himachal pradesh': 'Himachal Pradesh',
            'himachal': 'Himachal Pradesh', 'hp': 'Himachal Pradesh', 'jharkhand': 'Jharkhand',
            'karnataka': 'Karnataka', 'ka': 'Karnataka', 'kerala': 'Kerala', 'kl': 'Kerala',
            'madhya pradesh': 'Madhya Pradesh', 'mp': 'Madhya Pradesh', 'm.p.': 'Madhya Pradesh', 'm p': 'Madhya Pradesh',
            'maharashtra': 'Maharashtra', 'mh': 'Maharashtra', 'maharastra': 'Maharashtra', 
            'manipur': 'Manipur', 'meghalaya': 'Meghalaya', 'mizoram': 'Mizoram', 'nagaland': 'Nagaland',
            'orissa': 'Odisha', 'odisha': 'Odisha', 'punjab': 'Punjab', 'pb': 'Punjab',
            'rajasthan': 'Rajasthan', 'rj': 'Rajasthan', 'sikkim': 'Sikkim', 'tamil nadu': 'Tamil Nadu',
            'tamilnadu': 'Tamil Nadu', 'tn': 'Tamil Nadu', 'telangana': 'Telangana', 'ts': 'Telangana',
            'tripura': 'Tripura', 'up': 'Uttar Pradesh', 'uttar pradesh': 'Uttar Pradesh',
            'uttarakhand': 'Uttarakhand', 'uk': 'Uttarakhand', 'west bengal': 'West Bengal',
            'wb': 'West Bengal', 'westbengal': 'West Bengal', 'andaman': 'Andaman and Nicobar Islands', 'chandigarh': 'Chandigarh',
            'dadra': 'Dadra and Nagar Haveli and Daman & Diu', 'daman': 'Dadra and Nagar Haveli and Daman & Diu',
            'delhi': 'Delhi (National Capital Territory)', 'new delhi': 'Delhi (National Capital Territory)', 
            'nct of delhi': 'Delhi (National Capital Territory)', 'jammu': 'Jammu & Kashmir', 'j&k': 'Jammu & Kashmir',
            'jk': 'Jammu & Kashmir', 'ladakh': 'Ladakh', 'lakshadweep': 'Lakshadweep',
            'puducherry': 'Puducherry', 'pondicherry': 'Puducherry'
        }
        
        def clean_state(s):
            if not s: return ''
            s_lower = s.lower().strip()
            if s_lower in state_mapping: return state_mapping[s_lower]
            for k, v in state_mapping.items():
                if len(k) > 3 and k in s_lower: return v
            return s.strip().title()
            
        combined_df['State'] = combined_df['State'].apply(clean_state)
    
    def get_product_category(row):
        offering = str(row.get('Offering', '')).upper()
        prods = []
        if "ASSET" in offering: prods.append("ASSET")
        if "MINDSPARK" in offering: prods.append("Mindspark")
        if "CARES" in offering: prods.append("CARES")
        return " + ".join(prods) if prods else "No Products"
    
    combined_df['Product Category'] = combined_df.apply(get_product_category, axis=1)
    return combined_df


def get_prod_count(offering):
    if not offering or not isinstance(offering, str): return 0
    o = offering.upper()
    return sum(["ASSET" in o, "MINDSPARK" in o, "CARES" in o])

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371 
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# -------------------------------------------------------------------
# Main App
# -------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Ei Performance Explorer", layout="wide")
    st.title("📈 Ei Performance, Growth & Bulk Upload")

    # Session State
    if 'allocations' not in st.session_state: st.session_state.allocations = []
    if 'new_schools_data' not in st.session_state: st.session_state.new_schools_data = []

    # Get Data
    df = load_and_merge_data()
    if st.session_state.new_schools_data:
        df = pd.concat([df, pd.DataFrame(st.session_state.new_schools_data)], ignore_index=True)
    
    if df.empty:
        st.error("Data files not found.")
        return

    # Sidebar Filter
    st.sidebar.header("Global Filters")
    all_years = sorted(df['Academic Year'].unique().tolist())
    selected_years = st.sidebar.multiselect("Select Years for View", all_years, default=all_years)
    
    filtered_df = df[df['Academic Year'].isin(selected_years)].copy()
    unique_schools = filtered_df.drop_duplicates(subset=['School No', 'School Name', 'City']).copy()

    # Geocoding Mapping
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f: cache = json.load(f)
    else: cache = {}

    def save_cache(c):
        with open(CACHE_FILE, 'w') as f: json.dump(c, f, indent=2)

    def geocode_location(location):
        try:
            gmaps = googlemaps.Client(key=GOOGLE_MAPS_KEY)
            res = gmaps.geocode(location)
            if res:
                lat, lon = res[0]['geometry']['location']['lat'], res[0]['geometry']['location']['lng']
                return {"lat": lat, "lon": lon}
        except: pass
        return None

    # Sidebar: Geocoding Controls
    st.sidebar.subheader("🌍 Geocoding & Locations")
    if st.sidebar.button("Geocode Missing Locations"):
        missing_cities = [c for c in df['City'].unique() if f"{c}, India" not in cache]
        if missing_cities:
            progress = st.sidebar.progress(0)
            for i, city in enumerate(missing_cities):
                loc_key = f"{city}, India"
                coords = geocode_location(loc_key)
                if coords: cache[loc_key] = coords
                progress.progress((i + 1) / len(missing_cities))
            save_cache(cache)
            st.sidebar.success(f"Geocoded {len(missing_cities)} locations!")
            st.rerun()
        else:
            st.sidebar.info("All cities are already geocoded.")
    
    st.sidebar.caption(f"Cached locations: {len(cache)}")


    def map_coords(row):
        # Precise key: School Name + City + State
        addr_precise = f"{row['School Name']}, {row['City']}, {row['State']}, India"
        if addr_precise in cache: return pd.Series([cache[addr_precise]['lat'], cache[addr_precise]['lon']])
        
        # Fallback key: City + State
        addr_city = f"{row['City']}, {row['State']}, India"
        if addr_city in cache: return pd.Series([cache[addr_city]['lat'], cache[addr_city]['lon']])
        
        return pd.Series([None, None])

    if not unique_schools.empty:
        unique_schools[['lat', 'lon']] = unique_schools.apply(map_coords, axis=1, result_type='expand')

    else: unique_schools['lat'], unique_schools['lon'] = None, None

    # Define Tabs
    tabs = st.tabs(["📍 Map View", "📊 Growth Analytics", "💰 Revenue Analysis", "📋 Raw Data", "🤝 Team Allocation", "➕ New Entry & Bulk", "📂 Master Sheet", "🎯 Range Planner", "🗺️ State Analytics"])
    tab1, tab2, tab_rev, tab3, tab4, tab5, tab6, tab7, tab8 = tabs


    with tab1:
        col_ctrl, col_viz = st.columns([1, 2])
        with col_ctrl:
            st.header("Search Area")
            en_rng = st.toggle("Radius Search", key="rng_t")
            if en_rng:
                loc_df = unique_schools[['City', 'State']].drop_duplicates().dropna()
                locs = sorted(loc_df.apply(lambda x: f"{x['City']}, {x['State']}", axis=1).unique())
                if locs:
                    center = st.selectbox("Center City:", options=locs)
                    addr_key = f"{center}, India"
                    if addr_key in cache:
                        c_lat, c_lon = cache[addr_key]['lat'], cache[addr_key]['lon']
                        rad = st.slider("Radius (km):", 1, 500, 100, key="tab1_rad")
                        map_display_df = unique_schools.copy()

                        map_display_df['distance'] = map_display_df.apply(
                            lambda r: calculate_distance(c_lat, c_lon, r['lat'], r['lon']) if not pd.isna(r['lat']) else 9999, axis=1
                        )
                        map_display_df = map_display_df[map_display_df['distance'] <= rad].copy()
                        st.success(f"Displaying {len(map_display_df)} schools in range.")
                        
                        # Area Analytics
                        st.divider()
                        st.subheader("📍 Area Analytics")
                        st.metric("Total Area Revenue", f"₹{map_display_df['Total Order Value (Exclusive GST)'].sum():,.0f}")
                        
                        # Product-wise Revenue
                        c_r1, c_r2, c_r3 = st.columns(3)
                        c_r1.metric("ASSET Rev", f"₹{map_display_df['ASSET Revenue'].sum():,.0f}")
                        c_r2.metric("MS Rev", f"₹{map_display_df['Mindspark Revenue'].sum():,.0f}")
                        c_r3.metric("CARES Rev", f"₹{map_display_df['CARES Revenue'].sum():,.0f}")
                        
                        st.subheader("Distribution")
                        if not map_display_df.empty:
                            area_prod_counts = map_display_df['Product Category'].value_counts()
                            # Product-wise Revenue Bar Chart
                            prod_revs = pd.Series({
                                'ASSET': map_display_df['ASSET Revenue'].sum(),
                                'Mindspark': map_display_df['Mindspark Revenue'].sum(),
                                'CARES': map_display_df['CARES Revenue'].sum()
                            })
                            c_p1, c_p2 = st.columns(2)
                            with c_p1: 
                                st.caption("Product Count")
                                st.bar_chart(area_prod_counts)
                            with c_p2:
                                st.caption("Product Revenue")
                                st.bar_chart(prod_revs)

                    else: map_display_df = unique_schools.copy()

                else: map_display_df = unique_schools.copy()
            else: map_display_df = unique_schools.copy()
            
            st.metric("Total Schools Shown", len(map_display_df))
            st.dataframe(map_display_df[['School Name', 'City', 'Offering', 'Total Order Value (Exclusive GST)']], width='stretch', hide_index=True)


        with col_viz:
            map_data = map_display_df.dropna(subset=['lat', 'lon'])

            if not map_data.empty:
                layer = pdk.Layer("ScatterplotLayer", map_data, get_position=["lon", "lat"], get_color=[255, 75, 75, 200], 
                                  get_radius=500, radius_min_pixels=3, radius_max_pixels=12, pickable=True, stroked=True)
                st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=map_data['lat'].mean(), longitude=map_data['lon'].mean(), zoom=5), map_style=pdk.map_styles.LIGHT, tooltip={"text": "{School Name}\n{City}"}))



    with tab2:
        st.header("📈 Growth Visualization")
        col_y1, col_y2 = st.columns(2)
        base_y = col_y1.selectbox("Base Year:", all_years, index=0)
        comp_y = col_y2.selectbox("Comparison Year:", all_years, index=len(all_years)-1)
        
        if base_y != comp_y:
            pivot = df.pivot_table(index=['School Name', 'City', 'Division', 'Zone'], columns='Academic Year', values='Offering', aggfunc='first').reset_index()
            # Flatten columns if MultiIndex
            if isinstance(pivot.columns, pd.MultiIndex):
                pivot.columns = [str(c[1]) if c[1] else str(c[0]) for c in pivot.columns.values]
            
            pivot['Base_C'] = pivot[base_y].fillna("").apply(get_prod_count)
            pivot['Comp_C'] = pivot[comp_y].fillna("").apply(get_prod_count)
            pivot['Added'] = pivot.apply(lambda r: 1 if pd.isna(r[base_y]) and not pd.isna(r[comp_y]) else 0, axis=1)
            pivot['Dropped'] = pivot.apply(lambda r: 1 if not pd.isna(r[base_y]) and pd.isna(r[comp_y]) else 0, axis=1)
            pivot['Upsell'] = pivot.apply(lambda r: 1 if not pd.isna(r[base_y]) and not pd.isna(r[comp_y]) and r['Comp_C'] > r['Base_C'] else 0, axis=1)

            
            # Flexible Aggregation Level
            agg_lvl = st.radio("Aggregation Level:", ["City", "Division", "Zone"], horizontal=True)
            
            city_group = pivot.groupby(agg_lvl).agg({
                'Added': 'sum', 
                'Dropped': 'sum', 
                'Upsell': 'sum'
            })
            
            # Robust Total Schools check for selected level
            total_counts = df.groupby(agg_lvl)['School Name'].nunique().to_frame('Total Schools')
            city_group = city_group.join(total_counts).fillna(0)
            
            city_sum_chart = city_group.sort_values('Added', ascending=False).head(10)
            st.subheader(f"Top 10 {agg_lvl}s Growth Trend")
            st.bar_chart(city_sum_chart[['Added', 'Dropped']])
            
            st.subheader(f"Performance Metrics ({agg_lvl} Level)")
            st.write(f"Comprehensive view of performance across all {agg_lvl}s.")
            st.dataframe(city_group.sort_values('Total Schools', ascending=False), width='stretch')

            # Visual Distribution
            st.divider()
            st.subheader("Product Distribution (All Schools)")
            df_prod = df[df['Academic Year'] == comp_y]
            if not df_prod.empty:
                prod_counts = df_prod['Product Category'].value_counts()
                st.bar_chart(prod_counts)



            st.divider()
            st.subheader("Detailed School-wise Growth Status")
            def get_status(r):
                if r['Added']: return "🟢 Added"
                if r['Dropped']: return "🔴 Dropped"
                if r['Upsell']: return "🔼 Upsell"
                return "⚪ Retained"
            pivot['Status'] = pivot.apply(get_status, axis=1)
            display_cols = ['School Name', 'City', base_y, comp_y, 'Status']
            st.dataframe(pivot[display_cols].sort_values('Status'), width='stretch', hide_index=True)

    with tab_rev:
        st.header("💰 School Revenue Analysis")
        rev_y = st.selectbox("Select Year for Revenue Analysis:", all_years, index=len(all_years)-1, key="rev_y_sel")
        df_rev = df[df['Academic Year'] == rev_y].copy()
        
        rev_col = 'Total Order Value (Exclusive GST)'
        def get_rev_bucket(val):
            lacs = val / 100000
            if lacs < 3: return "1. < 3 Lacs"
            if 3 <= lacs < 5: return "2. 3 - 5 Lacs"
            if 5 <= lacs < 10: return "3. 5 - 10 Lacs"
            if 10 <= lacs < 15: return "4. 10 - 15 Lacs"
            return "5. > 15 Lacs"
        
        df_rev['Revenue Bucket'] = df_rev[rev_col].apply(get_rev_bucket)
        
        # Summary View
        buckets = sorted(df_rev['Revenue Bucket'].unique())
        c_m1, c_m2 = st.columns([1, 2])
        with c_m1:
            st.subheader("Summary by Bucket")
            rev_summary = df_rev.groupby('Revenue Bucket').size().to_frame('No. of Schools').reset_index()
            st.dataframe(rev_summary, width='stretch', hide_index=True)
        
        with c_m2:
            st.subheader("Revenue Distribution")
            chart_type = st.radio("Group By:", ["Zone", "Division"], horizontal=True, key="rev_grp_rad")
            grp_rev = df_rev.groupby(chart_type)[rev_col].sum().reset_index()
            fig_pie = px.pie(grp_rev, values=rev_col, names=chart_type, hole=0.4, title=f"Revenue Share by {chart_type}")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()
        st.subheader("Product Distribution across Revenue Buckets & Division")
        # Product Category vs Revenue Bucket faceted by Division
        prod_rev_cross = df_rev.groupby(['Revenue Bucket', 'Product Category', 'Division']).size().reset_index(name='Count')
        fig_cross = px.bar(prod_rev_cross, x='Revenue Bucket', y='Count', color='Product Category', 
                           facet_col='Division', facet_col_wrap=2,
                           title="Products in each Revenue Segment by Division", barmode='stack')
        st.plotly_chart(fig_cross, use_container_width=True)


        st.divider()

        selected_bucket = st.multiselect("Filter by Revenue Bucket:", buckets, default=buckets)
        
        df_rev_filtered = df_rev[df_rev['Revenue Bucket'].isin(selected_bucket)]
        st.subheader(f"School Details ({len(df_rev_filtered)} schools)")
        display_rev_cols = ['School Name', 'City', 'Division', 'Zone', rev_col, 'Product Category']
        st.dataframe(df_rev_filtered[display_rev_cols].sort_values(rev_col, ascending=False), width='stretch', hide_index=True)


    with tab3:
        st.header("Raw Data & Operations")
        
        # Bulk Upload Section
        st.subheader("📤 Bulk Upload Additional Data")
        uploaded_file = st.file_uploader("Upload CSV for extra schools", type=['csv'])
        if uploaded_file:
            extra_df = pd.read_csv(uploaded_file)
            st.success(f"Uploaded {len(extra_df)} records!")
            st.dataframe(extra_df.head(), width='stretch')
            # Logic to merge or append could be added here if session state was persistent

        st.divider()
        st.subheader(f"Filtered Results ({len(filtered_df)} records)")
        st.dataframe(filtered_df, width='stretch')

    with tab4:
        st.header("🤝 Team Allocation")
        with st.form("alloc_form"):
            m_name, m_role = st.text_input("Name"), st.selectbox("Role", ["Academic Consultant", "Associate"])
            m_schools = st.multiselect("Pick Schools", options=sorted(unique_schools['School Name'].unique()))
            if st.form_submit_button("Assign"):
                if m_name and m_schools:
                    st.session_state.allocations.append({'Member': m_name, 'Role': m_role, 'Schools': ", ".join(m_schools), 'Count': len(m_schools)})
                    st.rerun()
        if st.session_state.allocations:
            st.data_editor(pd.DataFrame(st.session_state.allocations), width='stretch', num_rows="dynamic")

    with tab5:
        st.header("➕ New Entry & Bulk Upload")
        c_manual, c_bulk = st.columns(2)
        with c_manual:
            st.subheader("Individual Entry")
            with st.form("man_add"):
                n_name, n_city, n_year = st.text_input("School Name"), st.text_input("City"), st.selectbox("Year", all_years)
                if st.form_submit_button("Save"):
                    if n_name and n_city:
                        st.session_state.new_schools_data.append({'School Name': n_name, 'City': n_city, 'Academic Year': str(n_year), 'Offering': ''})
                        st.rerun()
        with c_bulk:
            st.subheader("Bulk CSV Upload")
            uploaded_file = st.file_uploader("Upload CSV", type="csv")
            if uploaded_file:
                bulk_df = pd.read_csv(uploaded_file).fillna("")
                if st.button("Process Bulk Upload"):
                    st.session_state.new_schools_data.extend(bulk_df.to_dict('records'))
                    st.success(f"Added {len(bulk_df)} schools!")
                    st.rerun()

    with tab6:
        st.header("📂 Master Allocation Sheet")
        def find_assignee(sn, r):
            for a in st.session_state.allocations:
                if 'Role' in a and a['Role'] == r and sn in [s.strip() for s in a['Schools'].split(",")]: return a['Member']
            return "Unassigned"
        master_data = []
        for _, row in unique_schools.iterrows():
            sn = row['School Name']
            master_data.append({'School Name': sn, 'City': row['City'], 'Offering': row['Offering'], 'Academic Consultant': find_assignee(sn, "Academic Consultant"), 'Associate': find_assignee(sn, "Associate")})
        st.dataframe(pd.DataFrame(master_data), width='stretch', hide_index=True)

    with tab7:
        st.header("🎯 Range & Coverage Planner")
        st.write("Plan and analyze coverage for specific city hubs.")
        
        # Hub Summary Table [NEW]
        st.subheader("🏙️ Hub Connectivity Summary")
        hub_summary = df.groupby('City')['School Name'].nunique().sort_values(ascending=False).to_frame('Total Schools')
        st.dataframe(hub_summary, width='stretch')
        
        st.divider()
        st.subheader("🔎 Individual Hub Analysis")
        c_h1, c_h2 = st.columns([1, 2])
        hub_city = c_h1.selectbox("Select Target City Hub:", options=sorted(df['City'].unique().tolist()), key="hub_sel")
        hub_rad = c_h2.slider("Target Radius (km):", 1, 500, 100, key="hub_rad_sld")

        
        # We need the hub's coords
        addr_hub = f"{hub_city}, India"
        if addr_hub in cache:
            h_lat, h_lon = cache[addr_hub]['lat'], cache[addr_hub]['lon']
            
            # Temporary filter for this tab
            range_schools = unique_schools.copy()
            range_schools['hub_distance'] = range_schools.apply(
                lambda r: calculate_distance(h_lat, h_lon, r['lat'], r['lon']) if not pd.isna(r['lat']) else 9999, axis=1
            )
            in_range = range_schools[range_schools['hub_distance'] <= hub_rad].copy()
            
            c_p1, c_p2 = st.columns(2)
            c_p1.metric("Schools in Hub Range", len(in_range))
            c_p2.metric("Total Hub Revenue", f"₹{in_range['Total Order Value (Exclusive GST)'].sum():,.0f}")
            
            # Map for Range Planner
            st.subheader("Range Map")
            hub_point = pd.DataFrame([{'lat': h_lat, 'lon': h_lon, 'School Name': 'HUB: ' + hub_city}])
            map_range_data = pd.concat([in_range.dropna(subset=['lat', 'lon']), hub_point], ignore_index=True)
            
            if not map_range_data.empty:
                view_state = pdk.ViewState(latitude=h_lat, longitude=h_lon, zoom=7)
                s_layer = pdk.Layer("ScatterplotLayer", in_range, get_position=["lon", "lat"], get_color=[255, 75, 75, 200], 
                                    get_radius=500, radius_min_pixels=3, radius_max_pixels=10, pickable=True)
                h_layer = pdk.Layer("ScatterplotLayer", hub_point, get_position=["lon", "lat"], get_color=[75, 75, 255, 255], 
                                    get_radius=1000, radius_min_pixels=6, radius_max_pixels=15, pickable=True)
                st.pydeck_chart(pdk.Deck(layers=[s_layer, h_layer], initial_view_state=view_state, map_style=pdk.map_styles.LIGHT, tooltip={"text": "{School Name}"}))


            st.subheader(f"Schools within {hub_rad}km of {hub_city}")
            if not in_range.empty:
                st.dataframe(in_range[['School Name', 'City', 'hub_distance', 'Offering']], width='stretch', hide_index=True)

            else:
                st.info("No schools found in this range. Try increasing the radius or ensure schools are geocoded.")
        else:
            st.warning(f"Geocoding data for {hub_city} not found.")
            if st.button(f"Geocode {hub_city} Now"):
                coords = geocode_location(addr_hub)
                if coords:
                    cache[addr_hub] = coords
                    save_cache(cache)
                    st.success(f"Geocoded {hub_city}!")
                    st.rerun()
                else:
                    st.error(f"Could not geocode {hub_city}. Please check the city name.")


    with tab8:
        st.header("🗺️ State & Product Analytics")
        if 'School Type' not in df.columns:
            df['School Type'] = 'Unknown'
            
        st.write("Detailed breakdown of school types and their purchased products across different states.")
        
        state_y = st.selectbox("Select Year:", all_years, index=len(all_years)-1, key="state_y_sel")
        df_state = df[df['Academic Year'] == state_y].copy()

        def categorize_school_type(x):
            val = str(x).lower()
            if 'retention' in val: return "Retention School"
            return "New & 1-Year School"
        
        df_state['Category'] = df_state['School Type'].apply(categorize_school_type)
        
        # Display Totals
        total_schools_yr = len(df_state)
        total_new_1yr = len(df_state[df_state['Category'] == "New & 1-Year School"])
        total_ret = len(df_state[df_state['Category'] == "Retention School"])
        
        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Total Schools", total_schools_yr)
        cm2.metric("New & 1-Year Schools", total_new_1yr)
        cm3.metric("Retention Schools", total_ret)
        
        st.divider()
        sel_cat = st.radio("Select Level to Visualize:", ["New & 1-Year School", "Retention School"], horizontal=True, key="cat_radio")
        df_cat = df_state[df_state['Category'] == sel_cat].copy()
        
        def prod_bucket(p):
            prods = p.split(' + ') if p != 'No Products' else []
            if len(prods) == 1:
                return f"Only {prods[0]}"
            elif len(prods) == 2:
                return "Combination of Two"
            elif len(prods) == 3:
                return "All Three"
            return "None"
        
        df_cat['Product Bucket'] = df_cat['Product Category'].apply(prod_bucket)

        st.subheader(f"State-Wise details for {sel_cat}")
        
        ALL_STATES_UTS = [
            'Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar',
            'Chandigarh', 'Chhattisgarh', 'Dadra and Nagar Haveli and Daman & Diu', 
            'Delhi (National Capital Territory)', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 
            'Jammu & Kashmir', 'Jharkhand', 'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep', 
            'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 
            'Odisha', 'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 
            'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal'
        ]
        
        base_df = pd.DataFrame({'State': ALL_STATES_UTS})

        if not df_cat.empty:
            state_pivot = pd.pivot_table(
                df_cat, 
                index='State', 
                columns='Product Bucket', 
                aggfunc='size', 
                fill_value=0
            ).reset_index()

            state_totals = df_cat.groupby('State').size().reset_index(name='Total Schools')
            state_summary = pd.merge(state_totals, state_pivot, on='State', how='left')
        else:
            state_summary = pd.DataFrame(columns=['State', 'Total Schools'])
            
        state_summary = pd.merge(base_df, state_summary, on='State', how='left').fillna(0)

        expected_cols = ["Only ASSET", "Only CARES", "Only Mindspark", "Combination of Two", "All Three"]
        for ec in expected_cols:
            if ec not in state_summary.columns:
                state_summary[ec] = 0

        disp_cols = ['State', 'Total Schools'] + expected_cols
        
        for col in ['Total Schools'] + expected_cols:
            state_summary[col] = state_summary[col].astype(int)
            
        st.dataframe(state_summary[disp_cols], width='stretch')

        st.subheader("📊 Visual Graph")
        if state_summary['Total Schools'].sum() > 0:
            chart_data = state_summary[state_summary['Total Schools'] > 0]
            fig = px.bar(chart_data.sort_values('Total Schools', ascending=False), x='State', y='Total Schools', 
                         title=f"Total Schools per State ({sel_cat})", 
                         labels={'Total Schools': 'Number of Schools'},
                         color='Total Schools',
                         color_continuous_scale=px.colors.sequential.Viridis)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No school data to plot for the selected filters.")

        st.divider()
        st.subheader("🗺️ Map View for Selected Category")
        sc_names = df_cat['School Name'].unique() if not df_cat.empty else []
        map_data_state = unique_schools[unique_schools['School Name'].isin(sc_names)].copy()
        map_data_state = map_data_state.dropna(subset=['lat', 'lon'])
        if not map_data_state.empty:
            color = [75, 255, 75, 200] if sel_cat == "New & 1-Year School" else [255, 75, 75, 200]
            layer = pdk.Layer(
                "ScatterplotLayer", map_data_state, 
                get_position=["lon", "lat"], get_color=color, 
                get_radius=500, radius_min_pixels=3, radius_max_pixels=12, pickable=True, stroked=True
            )
            st.pydeck_chart(pdk.Deck(
                layers=[layer], 
                initial_view_state=pdk.ViewState(latitude=map_data_state['lat'].mean(), longitude=map_data_state['lon'].mean(), zoom=4), 
                map_style=pdk.map_styles.LIGHT, tooltip={"text": "{School Name}\\n{City}"}
            ))
        else:
            st.info("No map data available for the selected category.")


if __name__ == "__main__":
    main()
