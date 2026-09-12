import json
from html import escape

import folium
import streamlit as st
from streamlit_folium import st_folium

try:
    from streamlit_js_eval import get_geolocation
except ImportError:
    get_geolocation = None
from src.database.connection import get_connection
from src.database.repository import (
    count_pois_by_category,
    count_pois_by_sector,
    search_pois,
)
from src.search.search_service import search_within_radius

STANDARD_MAP_MARKER_LIMIT = 250


st.set_page_config(
    page_title="Islamabad GeoIntel",
    page_icon="📍",
    layout="wide",
)

# Mobile-first presentation adjustments. These affect layout/spacing only;
# search, SQLite, geolocation and native Folium synchronization are unchanged.
st.markdown(
    """
    <style>
    /* Keep desktop spacing comfortable. */
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 2rem;
    }

    /* Prevent long metric labels and captions from feeling oversized. */
    [data-testid="stMetricLabel"] {
        line-height: 1.15;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 1.50rem;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
            padding-bottom: 1.25rem;
        }

        h1 {
            font-size: 1.75rem !important;
            line-height: 1.15 !important;
        }

        h2, h3 {
            margin-top: 0.65rem !important;
            margin-bottom: 0.4rem !important;
        }

        [data-testid="stMetric"] {
            padding-top: 0.2rem;
            padding-bottom: 0.2rem;
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.78rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.35rem;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.78rem;
            line-height: 1.3;
        }

        /* Make form controls easier to tap without wasting vertical space. */
        .stTextInput, .stSelectbox, .stNumberInput {
            margin-bottom: 0.15rem;
        }

        /* Allow wide result data to scroll horizontally on a phone. */
        [data-testid="stDataFrame"] {
            overflow-x: auto;
        }

        /* Keep Folium within the phone viewport width. */
        iframe {
            max-width: 100% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Native st_folium map clicks are synchronized to Python below.
# Legacy query-parameter handoff is no longer used.
origin_sync_received = False
st.markdown(
    """
    <div style="text-align: center;">
        <h1 style="margin-bottom: 0.25rem;">Islamabad GeoIntel</h1>
        <p style="
            font-size: 1.05rem;
            color: #6c757d;
            margin-top: 0;
            margin-bottom: 1.25rem;
        ">
            AI-assisted geographic intelligence and places discovery for Islamabad, Pakistan
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    connection = get_connection()

    try:
        category_counts = count_pois_by_category(connection)
        sector_counts = count_pois_by_sector(connection)

        poi_count = sum(
            row["poi_count"]
            for row in category_counts
        )

        category_count = len(category_counts)

        assigned_sector_count = sum(
            row["poi_count"]
            for row in sector_counts
        )

        unassigned_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM pois
            WHERE sector IS NULL
            """
        ).fetchone()[0]

        categories = [
            row["category"]
            for row in category_counts
        ]

        sectors = [
            row["sector"]
            for row in sector_counts
        ]

        st.subheader("Pilot Database")

        metric_1, metric_2, metric_3, metric_4 = st.columns(4)

        metric_1.metric(
            "Searchable POIs",
            f"{poi_count:,}",
        )

        metric_2.metric(
            "Categories",
            category_count,
        )

        metric_3.metric(
            "Sector-attributed POIs",
            f"{assigned_sector_count:,}",
        )

        metric_4.metric(
            "Sector-unassigned POIs",
            f"{unassigned_count:,}",
        )

        st.caption(
            "Pilot coverage: F-5, F-6 and F-7. "
            "Sector attribution is evidence-based; proximity is not used to infer a sector."
        )

        st.divider()

        st.subheader("Search Places")

        search_mode = st.radio(
            "Search mode",
            [
                "Standard Search",
                "Proximity Search",
            ],
            horizontal=True,
        )

        if "emergency_quick_search" not in st.session_state:
            st.session_state.emergency_quick_search = False

        emergency_col, clear_emergency_col = st.columns([3, 2])
        with emergency_col:
            if st.button(
                "🚨 Emergency POIs",
                use_container_width=True,
                help=(
                    "Show POIs explicitly classified as emergency in the "
                    "current OSM-derived pilot database."
                ),
            ):
                st.session_state.emergency_quick_search = True
                st.rerun()

        with clear_emergency_col:
            if st.session_state.emergency_quick_search:
                if st.button(
                    "Clear emergency",
                    use_container_width=True,
                ):
                    st.session_state.emergency_quick_search = False
                    st.rerun()

        if st.session_state.emergency_quick_search:
            st.warning(
                "Emergency mode shows only records explicitly classified as "
                "emergency in the current F-5/F-6/F-7 OSM pilot database. "
                "It is not a complete or authoritative emergency-services "
                "directory for Islamabad."
            )

        previous_search_mode = st.session_state.get(
            "previous_search_mode",
            "Standard Search",
        )
        entered_proximity_search = (
            search_mode == "Proximity Search"
            and previous_search_mode != "Proximity Search"
        )
        st.session_state.previous_search_mode = search_mode

        if entered_proximity_search:
            # A "Search around here" handoff already supplies an explicit origin.
            # Do not let automatic browser geolocation overwrite that selected
            # POI/map coordinate during the same reload.
            st.session_state.auto_location_pending = not origin_sync_received
            st.session_state.selected_origin_poi_id = None

        if origin_sync_received:
            st.session_state.auto_location_pending = False

        search_col_1, search_col_2, search_col_3 = st.columns(3)

        with search_col_1:
            name_query = st.text_input(
                "Name contains",
                placeholder="e.g. bank, hospital, cafe",
            )

        with search_col_2:
            if st.session_state.emergency_quick_search:
                st.text_input(
                    "Category",
                    value="emergency",
                    disabled=True,
                )
                selected_category = "emergency"
            else:
                selected_category = st.selectbox(
                    "Category",
                    ["All categories"] + categories,
                )

        with search_col_3:
            selected_sector = st.selectbox(
                "Sector",
                ["All sectors"] + sectors,
            )
        proximity_latitude = None
        proximity_longitude = None
        proximity_radius_km = None

        if "proximity_latitude" not in st.session_state:
            st.session_state.proximity_latitude = 33.7286213

        if "proximity_longitude" not in st.session_state:
            st.session_state.proximity_longitude = 73.0735239

        # Seed the keyed number_input widgets explicitly. Without these values,
        # Streamlit can initialize a bounded number_input at its minimum
        # (-90/-180), which is especially visible when browser geolocation is
        # unavailable (for example, a phone opening the LAN app over plain HTTP).
        if "proximity_latitude_input" not in st.session_state:
            st.session_state.proximity_latitude_input = float(
                st.session_state.proximity_latitude
            )
        if "proximity_longitude_input" not in st.session_state:
            st.session_state.proximity_longitude_input = float(
                st.session_state.proximity_longitude
            )

        # Repair the legacy invalid widget-state pair created by earlier builds.
        # A phone session that already received -90/-180 keeps those keyed values
        # across a normal refresh, so "initialize only if missing" is insufficient.
        legacy_minimum_pair = (
            float(st.session_state.get("proximity_latitude_input", 0.0)) == -90.0
            and float(st.session_state.get("proximity_longitude_input", 0.0)) == -180.0
        )
        if legacy_minimum_pair:
            st.session_state.proximity_latitude = 33.7286213
            st.session_state.proximity_longitude = 73.0735239
            st.session_state.proximity_latitude_input = 33.7286213
            st.session_state.proximity_longitude_input = 73.0735239
            st.session_state.selected_origin_poi_id = None
            st.session_state.browser_location_accuracy_m = None

        # Apply a POI/empty-map click captured on the previous Streamlit run.
        # This executes before the keyed number_input widgets are instantiated,
        # which is the only safe point to update their session-state values.
        pending_map_latitude = st.session_state.pop(
            "pending_map_latitude",
            None,
        )
        pending_map_longitude = st.session_state.pop(
            "pending_map_longitude",
            None,
        )

        if (
            pending_map_latitude is not None
            and pending_map_longitude is not None
        ):
            st.session_state.proximity_latitude = float(pending_map_latitude)
            st.session_state.proximity_longitude = float(pending_map_longitude)
            st.session_state.proximity_latitude_input = float(
                pending_map_latitude
            )
            st.session_state.proximity_longitude_input = float(
                pending_map_longitude
            )
            st.session_state.browser_location_accuracy_m = None
            st.session_state.auto_location_pending = False

        if "proximity_latitude_input" not in st.session_state:
            st.session_state.proximity_latitude_input = float(
                st.session_state.proximity_latitude
            )

        if "proximity_longitude_input" not in st.session_state:
            st.session_state.proximity_longitude_input = float(
                st.session_state.proximity_longitude
            )

        if "selected_origin_poi_id" not in st.session_state:
            st.session_state.selected_origin_poi_id = None

        if "browser_location_accuracy_m" not in st.session_state:
            st.session_state.browser_location_accuracy_m = None

        if search_mode == "Proximity Search":
            if (
                st.session_state.get("auto_location_pending", False)
                and not origin_sync_received
            ):
                if get_geolocation is None:
                    st.info(
                        "Automatic browser location requires the "
                        "'streamlit-js-eval' package. Manual coordinates "
                        "and map-click selection remain available."
                    )
                    st.session_state.auto_location_pending = False
                else:
                    browser_location = get_geolocation()

                    if browser_location:
                        if "error" in browser_location:
                            error_message = browser_location["error"].get(
                                "message",
                                "Browser location could not be obtained.",
                            )
                            st.warning(
                                "Automatic browser location was not available: "
                                f"{error_message} "
                                "This phone is opening the app over a local HTTP "
                                "address, where browser geolocation may be blocked. "
                                "You can still enter coordinates manually or "
                                "select a point on the map."
                            )
                            st.session_state.auto_location_pending = False
                        else:
                            coords = browser_location.get("coords", {})
                            browser_latitude = coords.get("latitude")
                            browser_longitude = coords.get("longitude")
                            browser_accuracy = coords.get("accuracy")

                            if (
                                browser_latitude is not None
                                and browser_longitude is not None
                            ):
                                st.session_state.proximity_latitude = float(
                                    browser_latitude
                                )
                                st.session_state.proximity_longitude = float(
                                    browser_longitude
                                )
                                st.session_state.proximity_latitude_input = float(
                                    browser_latitude
                                )
                                st.session_state.proximity_longitude_input = float(
                                    browser_longitude
                                )
                                st.session_state.selected_origin_poi_id = None
                                st.session_state.browser_location_accuracy_m = (
                                    float(browser_accuracy)
                                    if browser_accuracy is not None
                                    else None
                                )
                                st.session_state.auto_location_pending = False
                                st.rerun()

            st.markdown("#### Search Origin and Radius")

            proximity_col_1, proximity_col_2, proximity_col_3 = st.columns(3)

            with proximity_col_1:
                proximity_latitude = st.number_input(
                    "Latitude",
                    min_value=-90.0,
                    max_value=90.0,
                    format="%.7f",
                    key="proximity_latitude_input",
                )

            with proximity_col_2:
                proximity_longitude = st.number_input(
                    "Longitude",
                    min_value=-180.0,
                    max_value=180.0,
                    format="%.7f",
                    key="proximity_longitude_input",
                )

            with proximity_col_3:
                proximity_radius_km = st.number_input(
                    "Radius (km)",
                    min_value=0.1,
                    max_value=50.0,
                    value=2.0,
                    step=0.5,
                    format="%.1f",
                )

            # These are the exact coordinates that the SQLite proximity engine
            # will use on this run.
            st.session_state.proximity_latitude = float(proximity_latitude)
            st.session_state.proximity_longitude = float(proximity_longitude)

            location_accuracy = st.session_state.get(
                "browser_location_accuracy_m"
            )

            if location_accuracy is not None:
                st.caption(
                    "Browser location acquired. Reported accuracy: "
                    f"approximately {location_accuracy:.0f} metres. "
                    "The latitude/longitude fields above are the exact "
                    "coordinates returned by the browser."
                )

            st.caption(
                "When Proximity Search is opened, the browser requests your "
                "device location and uses the returned coordinates when available. "
                "The local OSM pilot database may not contain a name or POI for "
                "that exact location. Optional Google identification will be kept "
                "separate from the local database. You can still enter coordinates "
                "manually, tap a POI, or tap empty map space. The origin is not "
                "used to infer or assign a POI's sector."
            )

        category_filter = (
            None
            if selected_category == "All categories"
            else selected_category
        )

        sector_filter = (
            None
            if selected_sector == "All sectors"
            else selected_sector
        )

        name_filter = (
            name_query.strip()
            if name_query.strip()
            else None
        )

        if search_mode == "Proximity Search":
            st.info(
                "ACTIVE SQLite origin: "
                f"{proximity_latitude:.7f}, {proximity_longitude:.7f}"
            )

            results = search_within_radius(
                connection,
                latitude=proximity_latitude,
                longitude=proximity_longitude,
                radius_km=proximity_radius_km,
                category=category_filter,
                sector=sector_filter,
                name=name_filter,
                limit=1000,
            )
        else:
            results = search_pois(
                connection,
                category=category_filter,
                sector=sector_filter,
                name=name_filter,
                limit=1000,
            )

    finally:
        connection.close()

    st.write(f"**Results: {len(results):,}**")

    if results:
        result_rows = []

        for serial_number, row in enumerate(results, start=1):
            google_maps_url = (
                "https://www.google.com/maps/search/?api=1&query="
                f"{row['latitude']},{row['longitude']}"
            )

            result_row = {
                "S.No.": serial_number,
                "Name": row["name"] or "Unnamed POI",
                "Category": row["category"],
                "Subcategory": row["subcategory"] or "",
                "Sector": row["sector"] or "Unassigned",
                "Sector evidence": row["sector_status"],
            }

            if search_mode == "Proximity Search":
                result_row["Distance (km)"] = round(
                    row["distance_km"],
                    3,
                )

            result_row["Latitude"] = row["latitude"]
            result_row["Longitude"] = row["longitude"]
            result_row["Google Maps"] = google_maps_url

            result_rows.append(result_row)

        st.caption(
            "On a phone, swipe the results table horizontally for additional "
            "fields and the Google Maps link."
        )
        st.dataframe(
            result_rows,
            use_container_width=True,
            hide_index=True,
            height=380,
            column_config={
                "Google Maps": st.column_config.LinkColumn(
                    "Google Maps",
                    display_text="Open in Google Maps",
                ),
            },
        )

        st.markdown(
            '<div id="geointel-map-anchor"></div>',
            unsafe_allow_html=True,
        )
        st.subheader("Map")

        if search_mode == "Proximity Search":
            st.caption(
                "Tap a POI or empty map space to use that point as the proximity "
                "search origin. The database results and distances are recalculated "
                "automatically."
            )

        if search_mode == "Proximity Search":
            map_latitude = proximity_latitude
            map_longitude = proximity_longitude

            # Keep a useful street/POI-level view after selecting a new origin.
            proximity_zoom = 15 if proximity_radius_km <= 2.0 else 13
            map_zoom = proximity_zoom
        else:
            map_latitude = sum(
                row["latitude"] for row in results
            ) / len(results)

            map_longitude = sum(
                row["longitude"] for row in results
            ) / len(results)
            map_zoom = 13

        places_map = folium.Map(
            location=[map_latitude, map_longitude],
            zoom_start=map_zoom,
            control_scale=True,
        )
        # Performance optimization is deliberately limited to Standard Search.
        # Proximity Search keeps every returned POI marker because its native
        # marker/origin/circle synchronization has already been validated.
        map_results = results
        if (
            search_mode == "Standard Search"
            and len(results) > STANDARD_MAP_MARKER_LIMIT
        ):
            map_results = results[:STANDARD_MAP_MARKER_LIMIT]
            st.caption(
                f"Performance mode: showing {STANDARD_MAP_MARKER_LIMIT:,} of "
                f"{len(results):,} result markers on the Standard Search map. "
                "The results table remains complete."
            )

        for serial_number, row in enumerate(map_results, start=1):
            poi_name = row["name"] or "Unnamed POI"
            poi_sector = row["sector"] or "Unassigned"
            poi_subcategory = row["subcategory"] or ""

            try:
                poi_tags = json.loads(row["tags_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                poi_tags = {}

            poi_address = row["address"] or ""
            poi_phone = (
                poi_tags.get("contact:phone")
                or poi_tags.get("phone")
                or ""
            )
            poi_email = (
                poi_tags.get("contact:email")
                or poi_tags.get("email")
                or ""
            )
            poi_website = (
                poi_tags.get("contact:website")
                or poi_tags.get("website")
                or ""
            )
            poi_opening_hours = poi_tags.get("opening_hours") or ""

            google_maps_url = (
                "https://www.google.com/maps/search/?api=1&query="
                f"{row['latitude']},{row['longitude']}"
            )

            popup_lines = [
                f"<b>{serial_number}. {escape(str(poi_name))}</b>",
                f"Category: {escape(str(row['category']))}",
                f"Subcategory: {escape(str(poi_subcategory))}",
                f"Sector: {escape(str(poi_sector))}",
                f"Sector evidence: {escape(str(row['sector_status']))}",
                (
                    "Coordinates: "
                    f"{row['latitude']:.7f}, {row['longitude']:.7f}"
                ),
            ]

            if search_mode == "Proximity Search":
                popup_lines.append(
                    f"Distance: {row['distance_km']:.3f} km"
                )

            if poi_address:
                popup_lines.append(f"Address: {escape(str(poi_address))}")
            if poi_phone:
                popup_lines.append(f"Phone: {escape(str(poi_phone))}")
            if poi_email:
                popup_lines.append(f"Email: {escape(str(poi_email))}")
            if poi_opening_hours:
                popup_lines.append(
                    f"Opening hours: {escape(str(poi_opening_hours))}"
                )

            if poi_website:
                website_text = escape(str(poi_website))
                if str(poi_website).lower().startswith(("http://", "https://")):
                    popup_lines.append(
                        "Website: "
                        f'<a href="{website_text}" target="_blank" '
                        'rel="noopener noreferrer">Open website</a>'
                    )
                else:
                    popup_lines.append(f"Website: {website_text}")

            popup_lines.append(
                f'<a href="{google_maps_url}" target="_blank" '
                'rel="noopener noreferrer">Open in Google Maps</a>'
            )

            popup_html = "<br>".join(popup_lines)

            is_selected_origin = (
                search_mode == "Proximity Search"
                and st.session_state.selected_origin_poi_id == row["id"]
            )

            marker_icon = (
                folium.Icon(
                    color="red",
                    icon="star",
                    prefix="fa",
                )
                if is_selected_origin
                else folium.Icon(color="blue")
            )

            folium.Marker(
                location=[
                    row["latitude"],
                    row["longitude"],
                ],
                tooltip=f"{serial_number}. {poi_name}",
                popup=folium.Popup(
                    popup_html,
                    max_width=400,
                    show=is_selected_origin,
                ),
                icon=marker_icon,
                **{
                    "poi_id": row["id"],
                    "poi_latitude": row["latitude"],
                    "poi_longitude": row["longitude"],
                },
            ).add_to(places_map)

        search_radius_circle = None

        if search_mode == "Proximity Search":
            search_radius_circle = folium.Circle(
                location=[
                    proximity_latitude,
                    proximity_longitude,
                ],
                radius=proximity_radius_km * 1000,
                tooltip=f"Search radius: {proximity_radius_km:.1f} km",
                weight=2,
                fill=False,
            )
            search_radius_circle.add_to(places_map)

        if (
            search_mode == "Proximity Search"
            and st.session_state.selected_origin_poi_id is None
        ):
            folium.CircleMarker(
                location=[
                    proximity_latitude,
                    proximity_longitude,
                ],
                radius=12,
                tooltip="Search origin",
                popup=folium.Popup(
                    (
                        "<b>Proximity Search Origin</b><br>"
                        f"Latitude: {proximity_latitude:.7f}<br>"
                        f"Longitude: {proximity_longitude:.7f}<br>"
                        f"Radius: {proximity_radius_km:.1f} km"
                    ),
                    max_width=300,
                ),
                weight=4,
                fill=True,
                fill_opacity=1.0,
            ).add_to(places_map)

            folium.Marker(
                location=[
                    proximity_latitude,
                    proximity_longitude,
                ],
                tooltip="Search origin",
                icon=folium.Icon(
                    color="red",
                    icon="crosshairs",
                    prefix="fa",
                ),
            ).add_to(places_map)

        # Keep one stable Streamlit/Folium component.  The prior version changed
        # the component key whenever the origin changed, which forced a complete
        # remount after the click-triggered rerun and caused an additional dim/
        # redraw cycle.  Native st_folium click state is sufficient for Python
        # synchronization; the generated Folium map already contains the new
        # origin marker and radius circle on the rerun.
        map_state = st_folium(
            places_map,
            use_container_width=True,
            height=500,
            returned_objects=["last_object_clicked", "last_clicked"],
            key="places_map",
        )

        # Robust Python-side map synchronization.
        # Unlike the previous iframe/URL approach, st_folium itself returns the
        # clicked coordinates to Python.  Python then updates the exact widget
        # state used by search_within_radius() and reruns the app.
        if search_mode == "Proximity Search" and map_state:
            object_click = map_state.get("last_object_clicked")
            map_click = map_state.get("last_clicked")

            selected_click = None
            click_kind = None

            if (
                isinstance(object_click, dict)
                and object_click.get("lat") is not None
                and object_click.get("lng") is not None
            ):
                selected_click = object_click
                click_kind = "poi"
            elif (
                isinstance(map_click, dict)
                and map_click.get("lat") is not None
                and map_click.get("lng") is not None
            ):
                selected_click = map_click
                click_kind = "map"

            if selected_click is not None:
                clicked_latitude = float(selected_click["lat"])
                clicked_longitude = float(selected_click["lng"])
                click_signature = (
                    click_kind,
                    round(clicked_latitude, 7),
                    round(clicked_longitude, 7),
                )

                if (
                    st.session_state.get("last_native_map_click")
                    != click_signature
                ):
                    st.session_state.last_native_map_click = click_signature

                    # The latitude/longitude number_input widgets have already
                    # been instantiated earlier in this run. Streamlit forbids
                    # changing their keyed state now. Store the clicked origin
                    # in temporary pending keys; the next run applies these
                    # values BEFORE the widgets are created.
                    st.session_state.pending_map_latitude = clicked_latitude
                    st.session_state.pending_map_longitude = clicked_longitude
                    st.session_state.browser_location_accuracy_m = None
                    st.session_state.auto_location_pending = False

                    # If the clicked coordinate is one of the displayed POIs,
                    # retain its database id so it can render as the selected
                    # red marker after the rerun.
                    selected_poi_id = None
                    if click_kind == "poi":
                        for candidate in results:
                            if (
                                abs(
                                    float(candidate["latitude"])
                                    - clicked_latitude
                                )
                                < 0.0000001
                                and abs(
                                    float(candidate["longitude"])
                                    - clicked_longitude
                                )
                                < 0.0000001
                            ):
                                selected_poi_id = candidate["id"]
                                break

                    st.session_state.selected_origin_poi_id = selected_poi_id
                    st.rerun()


    else:
        st.info("No places match the selected filters.")
except Exception as exc:
    st.error("Unable to load Islamabad GeoIntel.")
    st.exception(exc)
