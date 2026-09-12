# Islamabad GeoIntel



Islamabad GeoIntel is an AI-assisted geographic intelligence and point-of-interest (POI) discovery application for Islamabad, Pakistan.



The project builds and queries its own local geographic database using OpenStreetMap (OSM)-derived data. It provides structured search, proximity search, deterministic natural-language queries, interactive mapping, category statistics, and emergency-record discovery through a Streamlit web interface.



## Project Status



The current implementation is a validated pilot covering Islamabad sectors:



\- F-5

\- F-6

\- F-7



The pilot database contains 800 searchable POIs across 14 normalized categories.



This is a proof-of-concept geographic intelligence system and must not be interpreted as a complete or authoritative directory of Islamabad.



## Core Features



### Standard Search



Search and filter the local POI database by:



\- name

\- category

\- subcategory

\- sector



### Proximity Search



Search around a geographic origin using:



\- browser/device location when available

\- manually entered coordinates

\- a POI selected from the map

\- an arbitrary point selected on the map



Distances are calculated locally using the Haversine formula.



### Natural-Language Search



The application includes a deterministic natural-language query layer that converts supported user queries into structured database operations.



Examples include:



\- `hospitals in F-6`

\- `food in F-6`

\- `nearest hospital`

\- `emergency within 2 km`



The natural-language layer is deliberately constrained and auditable. Unsupported queries fail safely rather than fabricating locations or results.



No external generative-AI API is required for this functionality.



### Interactive Mapping



The Streamlit interface uses Folium and OpenStreetMap mapping.



Proximity mode supports:



\- current search origin

\- radius visualization

\- POI markers

\- map-based origin selection

\- recalculated distances after origin changes



Ordinary Standard Search map rendering is capped for performance while the complete result table remains available.



### Emergency Quick Search



Emergency is maintained as a first-class normalized category.



Emergency results reflect only records present in the pilot OSM-derived database and must not be treated as a complete emergency-services directory.



### Google Maps Navigation



POI coordinates can be opened using outbound Google Maps navigation links.



The application does not scrape Google Maps and does not use the Google Places, Geocoding, or Geolocation APIs.



## Data Source



The primary geographic data source is OpenStreetMap.



OpenStreetMap data is made available under the Open Database License (ODbL). Appropriate OpenStreetMap attribution must be retained when using or presenting OSM-derived data.



The application separates data acquisition, normalization, storage, search, geographic calculations, and user-interface logic.



## Pilot Data Methodology



The pilot was developed using OSM/Overpass discovery around F-5, F-6, and F-7.



The sector reference coordinates used during data discovery were reference points and were not treated as authoritative sector boundaries.



Because consistent sector polygons were not available in the pilot source data, sector attribution uses explicit OSM tag/address evidence.



A POI is not assigned to a sector merely because it is geographically nearest to a sector reference point.



Records without sufficiently reliable sector evidence remain unassigned or ambiguous.



## Validated Pilot Database



Current deployment database:



\- Searchable POIs: 800

\- Unique OSM identities: 800

\- Normalized categories: 14

\- Sector-attributed POIs: 92

\- Database integrity check: `ok`



The 14 normalized categories are:



\- accommodation

\- education

\- emergency

\- financial

\- food\_drink

\- government

\- healthcare

\- other\_amenity

\- professional\_services

\- public\_service

\- recreation

\- religion

\- retail

\- transport



Database uniqueness is enforced using the combination of OSM object type and OSM object ID.



## Architecture



The principal data flow is:



```text

OpenStreetMap / Overpass

&#x20;         |

&#x20;         v

&#x20;  Data Acquisition

&#x20;         |

&#x20;         v

&#x20;    Normalization

&#x20;         |

&#x20;         v

&#x20;      SQLite

&#x20;         |

&#x20;         +--------------------+

&#x20;         |                    |

&#x20;         v                    v

&#x20;Search / Geo Engine    Natural-Language Layer

&#x20;         |                    |

&#x20;         +----------+---------+

&#x20;                    |

&#x20;                    v

&#x20;             Streamlit UI

&#x20;                    |

&#x20;                    v

&#x20;           Folium / OSM Map
