# UrbanPulse

UrbanPulse is a city exploration tool that helps people see where activity, relevance, and opportunities are concentrated around them. Instead of browsing venues one by one, users can visualize the *pulse* of a city and quickly understand where life is happening.

---

## What it does

UrbanPulse aggregates signals from places and events — such as relevance, popularity, crowd level, and urgency — and converts them into a spatial visualization.

Each location receives a contextual score, and the frontend renders these scores as 3D columns on a map, allowing users to explore areas based on their interests or mood.

The goal is not to recommend a single destination, but to help people understand their environment and discover nearby opportunities more naturally.

---

## How it works

### Backend

The backend is built with **FastAPI** and performs several steps:

- Loads places and events data for Madison, WI  
- Enriches venues with popularity and crowd signals  
- Computes keyword relevance using TF-IDF cosine similarity  
- Calculates urgency based on time-sensitive events and closing hours  
- Combines signals into a contextual score depending on exploration mode  
- Returns a ranked list of entities for visualization  

### Frontend

The frontend is built with **React** and **deck.gl**.

- Displays scored locations as 3D columns on a map  
- Allows users to input keywords or select exploration modes  
- Updates the visualization dynamically to reflect different city signals  
- Shows details and score breakdowns on interaction  

---

## Tech stack

### Backend
- Python  
- FastAPI  
- TF-IDF / cosine similarity scoring  
- BestTime API integration (foot-traffic signals)  

### Frontend
- React  
- deck.gl  
- Mapbox  

---

## Why we built this

Cities offer countless opportunities, but most people lack awareness of what’s happening around them in the moment.

UrbanPulse aims to make those signals visible so people can explore with more confidence and discover experiences they might otherwise miss.

---

## Running the project

### Backend

```bash
cd backend
python3 api.py
```
### Frontend
```bash
cd frontend
npm install
npm run dev
```
### Future improvements
- Real-time event ingestion
- More cities and larger datasets
- Personalized weighting based on user preferences
- Richer semantic matching using embeddings
- Live crowd updates and streaming signals
