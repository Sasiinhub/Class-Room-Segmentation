from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
import json
import os
import shutil
import io
import sqlite3
import datetime

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATA_DIR = "data"
HISTORY_DIR = os.path.join(DATA_DIR, "history")
DB_FILE = os.path.join(DATA_DIR, "educluster.db")

# Ensure directories exist
os.makedirs(HISTORY_DIR, exist_ok=True)

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            batch_name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER,
            student_id TEXT,
            exam_score REAL,
            participation_frequency REAL,
            logical_understanding REAL,
            curiosity_level REAL,
            self_learning REAL,
            question_frequency REAL,
            depth_of_doubts REAL,
            assignment_completion REAL,
            engagement_score REAL,
            cluster INTEGER,
            deviation REAL,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Global state
analysis_results = None # Starts empty, waiting for upload

def perform_analysis(filepath):
    """
    Loads data from filepath, performs clustering and PCA.
    """
    print(f"Loading data from {filepath}...")
    if not os.path.exists(filepath):
         print("Data file not found.")
         return None

    try:
        df = pd.read_csv(filepath)
        
        # Clean Columns: Normalize to snake_case for robust matching
        # Map specific human readable names to internal names
        column_map = {
            'Student ID': 'student_id',
            'Exam Score': 'exam_score',
            'Participation Frequency': 'participation_frequency',
            'Assignment Completion': 'assignment_completion',
            'Question Frequency': 'question_frequency',
            'Depth of Doubts': 'depth_of_doubts',
            'Logical Understanding': 'logical_understanding',
            'Curiosity Level': 'curiosity_level',
            'Self-Learning Capability': 'self_learning',
            'Self Learning': 'self_learning' # Alternate
        }
        df.rename(columns=column_map, inplace=True)
        
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

    # Features
    features = [
        'participation_frequency', 'assignment_completion', 'depth_of_doubts', 
        'curiosity_level', 'self_learning', 'question_frequency', 
        'exam_score', 'logical_understanding'
    ]
    
    # Validation
    missing_cols = [col for col in features if col not in df.columns]
    if missing_cols:
        return None

    X = df[features]
    
    # 1. Standardization
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 2. Clustering (K-Means)
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled)
    
    # 3. PCA
    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(X_scaled)
    
    # 4. Prepare Result
    df['temp_cluster'] = clusters
    df['x'] = pca_result[:, 0]
    df['y'] = pca_result[:, 1]
    
    # Fixed Groups
    cluster_profiles = {
        0: {"name": "Balanced Achievers", "description": "High Grades & High Engagement", "count": 0, "stats": {}},
        1: {"name": "Rote Learners", "description": "High Grades but Low Engagement", "count": 0, "stats": {}},
        2: {"name": "Hardworking Strugglers", "description": "High Engagement but Low Grades", "count": 0, "stats": {}},
        3: {"name": "Needs Support / Disengaged", "description": "Low Grades & Low Engagement", "count": 0, "stats": {}}
    }
    
    SCORE_THRESHOLD = 60
    ENGAGEMENT_THRESHOLD_HIGH = 50
    ENGAGEMENT_THRESHOLD_LOW = 65

    empty_stats = {feat: 0 for feat in features}
    for k in cluster_profiles:
        cluster_profiles[k]['stats'] = empty_stats.copy()

    for i in range(4):
        cluster_data = df[df['temp_cluster'] == i]
        if len(cluster_data) == 0: continue

        profile = cluster_data[features].mean().to_dict()
        count = int(len(cluster_data))
        
        avg_exam = profile['exam_score']
        engagement_features = [
            profile['participation_frequency'] * 10,
            profile['curiosity_level'] * 10,
            profile['question_frequency'] * 10,
            profile['self_learning'] * 10,
            profile['logical_understanding'] * 10,
            profile['assignment_completion']
        ]
        avg_engagement = sum(engagement_features) / len(engagement_features)

        # Map to Fixed ID
        target_id = 3
        if avg_exam >= SCORE_THRESHOLD:
            if avg_engagement >= ENGAGEMENT_THRESHOLD_HIGH: target_id = 0
            else: target_id = 1
        else:
            if avg_engagement >= ENGAGEMENT_THRESHOLD_LOW: target_id = 2
            else: target_id = 3

        # Update Fixed Group
        current_fixed = cluster_profiles[target_id]
        prev_count = current_fixed['count']
        total_count = prev_count + count
        
        if prev_count == 0:
            current_fixed['stats'] = profile
        else:
            for key in profile:
                old_val = current_fixed['stats'][key]
                new_val = profile[key]
                current_fixed['stats'][key] = ((old_val * prev_count) + (new_val * count)) / total_count
        
        current_fixed['count'] = total_count
        df.loc[df['temp_cluster'] == i, 'cluster'] = target_id

    df = df.drop(columns=['temp_cluster'])
    df['cluster'] = df['cluster'].fillna(3).astype(int)

    # Composite Score & Deviation
    def calc_student_engage(row):
        score = (row['participation_frequency']*10 + 
                 row['curiosity_level']*10 + 
                 row['question_frequency']*10 + 
                 row['self_learning']*10 + 
                 row['logical_understanding']*10 + 
                 row['assignment_completion']) / 6
        return score

    df['engagement_score'] = df.apply(calc_student_engage, axis=1)
    # Create Composite Score (Linear) - Still useful for rankings
    df['composite_score'] = (df['exam_score'] * 0.5) + (df['engagement_score'] * 0.5)
    
    # NEW IDEA: Euclidean Distance from Mastery (100, 100)
    # This treats Exam and Engagement as a single 2D entity.
    # Gap = sqrt( (100-Exam)^2 + (100-Engagement)^2 )
    # 0 = Perfect Mastery. High Value = High Deviation.
    df['deviation'] = np.sqrt(np.power(100 - df['exam_score'], 2) + np.power(100 - df['engagement_score'], 2))
    
    class_mean = df['composite_score'].mean()
    df = df.fillna(0) 

    return {
        "students": df.to_dict(orient='records'),
        "clusters": cluster_profiles,
        "class_stats": {
            "mean_score": class_mean,
            "std_dev": df['composite_score'].std()
        }
    }

# API Endpoints

@app.get("/api/data")
def get_data():
    """Returns current analysis or None if empty."""
    if not analysis_results:
        return {"empty": True, "message": "No data loaded. Please upload a CSV."}
    return analysis_results

@app.get("/api/history")
def get_history():
    """List all saved snapshots."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, timestamp, description, batch_name FROM snapshots ORDER BY id DESC")
    snapshots = [dict(row) for row in c.fetchall()]
    conn.close()
    return snapshots

@app.get("/api/history/{snapshot_id}")
def load_snapshot(snapshot_id: int):
    """Load a specific snapshot into the active analysis."""
    global analysis_results
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT filename FROM snapshots WHERE id = ?", (snapshot_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    filename = row[0]
    filepath = os.path.join(HISTORY_DIR, filename)
    
    results = perform_analysis(filepath)
    if results:
        analysis_results = results
        return {"message": f"Loaded snapshot {snapshot_id}", "data": results}
    else:
        raise HTTPException(status_code=500, detail="Failed to analyze snapshot")

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    batch_name: str = Form(...),
    description: str = Form(None)
):
    global analysis_results
    try:
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"snapshot_{timestamp}.csv"
        filepath = os.path.join(HISTORY_DIR, safe_filename)
        
        # Save file
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Analyze first to validate
        new_results = perform_analysis(filepath)
        if not new_results:
            os.remove(filepath) # Cleanup
            return JSONResponse(status_code=400, content={"error": "Invalid CSV file"})
            
        # Save to DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Default description if empty
        if not description:
            description = f"Upload {timestamp}"

        c.execute("INSERT INTO snapshots (filename, original_filename, description, batch_name) VALUES (?, ?, ?, ?)",
                  (safe_filename, file.filename, description, batch_name))
        new_id = c.lastrowid
        
        # Save Student Data for this snapshot
        students_pd = pd.DataFrame(new_results['students'])
        for _, row in students_pd.iterrows():
            c.execute('''INSERT INTO students 
                         (snapshot_id, student_id, exam_score, participation_frequency, 
                          logical_understanding, curiosity_level, self_learning, 
                          question_frequency, depth_of_doubts, assignment_completion,
                          engagement_score, cluster, deviation)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (new_id, row['student_id'], row['exam_score'], row['participation_frequency'],
                       row['logical_understanding'], row['curiosity_level'], row['self_learning'],
                       row['question_frequency'], row['depth_of_doubts'], row['assignment_completion'],
                       row['engagement_score'], int(row['cluster']), row['deviation']))
        
        conn.commit()
        conn.close()
        
        # Update active state
        analysis_results = new_results
        return {"message": "Upload successful", "snapshot_id": new_id}
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/export")
def export_data():
    global analysis_results
    if not analysis_results or "students" not in analysis_results:
        return {"error": "No data available to export"}, 400
        
    try:
        students = analysis_results["students"]
        clusters = analysis_results["clusters"]
        df_export = pd.DataFrame(students)
        
        cluster_map = {i: clusters[i]['name'] for i in clusters}
        df_export['cluster_name'] = df_export['cluster'].map(cluster_map)
        
        cols = ['student_id', 'cluster_name', 'cluster', 'exam_score', 'participation_frequency', 
                'assignment_completion', 'depth_of_doubts', 'curiosity_level', 
                'self_learning', 'question_frequency', 'logical_understanding']
        
        final_cols = [c for c in cols if c in df_export.columns]
        df_export = df_export[final_cols]
        
        stream = io.StringIO()
        df_export.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=student_clusters.csv"
        return response
        
    except Exception as e:
        return {"error": str(e)}, 500

@app.get("/api/trend")
def get_batch_trend(batch_name: str):
    """
    Analyzes historical snapshots for a specific batch.
    Returns trend data points (history) and forecast (future).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Needs at least 2 snapshots for trend
    c.execute("""
        SELECT id, timestamp, description 
        FROM snapshots 
        WHERE batch_name = ? 
        ORDER BY timestamp ASC
    """, (batch_name,))
    snapshots = c.fetchall()
    
    if len(snapshots) < 2:
        conn.close()
        return JSONResponse(status_code=400, content={"error": "Need at least 2 snapshots to calculate trend."})
    
    history_data = [] # List of {date, exam_avg, engage_avg}
    
    # Collect History Data
    for snap in snapshots:
        snap_id = snap[0]
        timestamp = snap[1]
        desc = snap[2]
        
        # Get Averages from Students Table
        df = pd.read_sql_query(f"SELECT exam_score, engagement_score FROM students WHERE snapshot_id = {snap_id}", conn)
        if not df.empty:
            history_data.append({
                "id": snap_id,
                "date": timestamp,
                "label": desc,
                "exam_avg": df['exam_score'].mean(),
                "engage_avg": df['engagement_score'].mean()
            })
            
    conn.close()
    
    if not history_data:
         return JSONResponse(status_code=400, content={"error": "No valid student data found in snapshots."})

    # Prepare for Regression
    df_trend = pd.DataFrame(history_data)
    # Convert dates to ordinal for regression X-axis
    df_trend['date_obj'] = pd.to_datetime(df_trend['date'])
    df_trend['date_ordinal'] = df_trend['date_obj'].apply(lambda x: x.toordinal())
    
    # Function to forecast
    def get_forecast(y_col):
        X = df_trend[['date_ordinal']]
        y = df_trend[y_col]
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Forecast next step (approx 1 average interval duration)
        # Calculate avg delta time
        avg_delta = (df_trend['date_ordinal'].max() - df_trend['date_ordinal'].min()) / max(1, (len(df_trend) - 1))
        # Minimum step if too small (e.g. same day uploads) -> 7 days
        step = max(avg_delta, 7) 
        
        next_date_ordinal = df_trend['date_ordinal'].max() + step
        next_val = model.predict([[next_date_ordinal]])[0]
        
        # Calculate MAE (Error Margin)
        preds = model.predict(X)
        mae = mean_absolute_error(y, preds)
        
        return next_val, mae, datetime.date.fromordinal(int(next_date_ordinal)).strftime("%Y-%m-%d")

    # Forecast Exam
    exam_next, exam_mae, next_date = get_forecast('exam_avg')
    # Forecast Engagement
    engage_next, engage_mae, _ = get_forecast('engage_avg')
    
    return {
        "batch_name": batch_name,
        "history": history_data,
        "forecast": {
            "date": next_date,
            "exam_predicted": min(100, max(0, exam_next)), # Clamp 0-100
            "exam_mae": exam_mae,
            "engage_predicted": min(100, max(0, engage_next)),
            "engage_mae": engage_mae
        }
    }

# Serve Static Files
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
