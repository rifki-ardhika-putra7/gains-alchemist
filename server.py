from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import datetime as dt
import os
import json

app = Flask(__name__)
CORS(app)

# --- KONFIGURASI FILES ---
CSV_FILE = 'gym_data_clean.csv'
CONFIG_FILE = 'user_config.json'

# --- HELPER: LOAD & SAVE CONFIG (BERAT BADAN) ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"bodyweight": 65} # Default 65kg

def save_config(bw):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"bodyweight": float(bw)}, f)

# --- HELPER: CLEANING DATA OTOMATIS ---
def clean_and_process_data(raw_df):
    # Mapping nama kolom biar standar
    rename_map = {'Title': 'exercise', 'Date': 'date', 'Weight': 'weight', 'Reps': 'reps'}
    raw_df.rename(columns=rename_map, inplace=True)
    raw_df.columns = [x.lower() for x in raw_df.columns]
    
    # Validasi Kolom
    if not {'exercise', 'date', 'weight', 'reps'}.issubset(raw_df.columns):
        return pd.DataFrame()
    
    # Konversi Tipe Data
    raw_df['date'] = pd.to_datetime(raw_df['date'], errors='coerce')
    raw_df['weight'] = pd.to_numeric(raw_df['weight'], errors='coerce')
    raw_df['reps'] = pd.to_numeric(raw_df['reps'], errors='coerce')
    
    # Hapus Data Sampah & Data Lama (Pre-2024)
    raw_df.dropna(subset=['date', 'weight', 'reps'], inplace=True)
    raw_df = raw_df[(raw_df['weight'] > 0) & (raw_df['reps'] > 0)]
    raw_df = raw_df[raw_df['date'].dt.year >= 2024]
    
    # Hitung 1RM & Volume
    raw_df['volume'] = raw_df['weight'] * raw_df['reps']
    raw_df['e1rm'] = raw_df['weight'] * (1 + (raw_df['reps'] / 30))
    raw_df['e1rm'] = raw_df['e1rm'].round(2)
    
    if 'set_type' not in raw_df.columns:
        raw_df['set_type'] = 'NORMAL_SET'
        
    return raw_df.sort_values(by='date')

# --- LOAD DATA AWAL ---
try:
    df_raw = pd.read_csv(CSV_FILE)
    df = clean_and_process_data(df_raw)
    print("✅ Data Loaded Successfully")
except:
    print("⚠️ CSV Kosong. Menunggu Upload.")
    df = pd.DataFrame(columns=['date', 'exercise', 'weight', 'reps', 'volume', 'e1rm'])

# --- HELPER: HITUNG RANK ---
def calculate_rank(exercise_name, one_rm, bw):
    if one_rm == 0 or bw == 0: return "-"
    ratio = one_rm / bw
    name = exercise_name.lower()
    rank = "UNRANKED"
    
    # Compound Movements
    if any(x in name for x in ['bench', 'press', 'squat', 'deadlift', 'row', 'dips']):
        if ratio < 0.8: rank = "BEGINNER"
        elif 0.8 <= ratio < 1.2: rank = "INTERMEDIATE"
        elif 1.2 <= ratio < 1.5: rank = "ADVANCED"
        elif ratio >= 1.5: rank = "THE PUNISHER"
    # Isolation Movements
    elif any(x in name for x in ['curl', 'extension', 'raise', 'pushdown', 'fly']):
        if ratio < 0.4: rank = "BEGINNER"
        elif 0.4 <= ratio < 0.7: rank = "INTERMEDIATE"
        elif ratio >= 0.7: rank = "ELITE ARMS"
    return rank

# --- HELPER: GROUP OTOT ---
def get_muscle_group(exercise_name):
    name = exercise_name.lower()
    if any(x in name for x in ['bench', 'fly', 'push up', 'press']): return 'CHEST'
    if any(x in name for x in ['squat', 'leg', 'calf', 'deadlift', 'lunge']): return 'LEGS'
    if any(x in name for x in ['row', 'pull', 'chin', 'lat']): return 'BACK'
    if any(x in name for x in ['curl', 'bicep']): return 'BICEPS'
    if any(x in name for x in ['extension', 'pushdown', 'skull', 'dips']): return 'TRICEPS'
    if any(x in name for x in ['raise', 'face pull', 'shoulder']): return 'SHOULDERS'
    return 'OTHER'

# --- API ROUTES ---

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        data = request.json
        bw = data.get('bodyweight')
        if bw:
            save_config(bw)
            return jsonify({"message": "Saved", "bodyweight": bw})
        return jsonify({"error": "Invalid"}), 400
    else:
        return jsonify(load_config())

@app.route('/api/upload', methods=['POST'])
def upload_csv():
    global df
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    
    try:
        raw_df = pd.read_csv(file)
        clean_df = clean_and_process_data(raw_df)
        if clean_df.empty: return jsonify({"error": "Format Salah/Kosong"}), 400
        
        df = clean_df
        df.to_csv(CSV_FILE, index=False)
        return jsonify({"message": "Success! Data Updated."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/exercises', methods=['GET'])
def get_exercises():
    if df.empty: return jsonify([])
    return jsonify(sorted(df['exercise'].unique().tolist()))

@app.route('/api/anatomy', methods=['GET'])
def get_anatomy():
    if df.empty: return jsonify({})
    temp = df.copy()
    temp['muscle'] = temp['exercise'].apply(get_muscle_group)
    stats = temp.groupby('muscle')['volume'].sum().reset_index()
    return jsonify({ "labels": stats['muscle'].tolist(), "data": stats['volume'].tolist() })

@app.route('/api/predict', methods=['POST'])
def predict():
    if df.empty: return jsonify({"error": "Upload Data Dulu!"})
    data = request.json
    target_ex = data.get('exercise')
    
    sub_df = df[df['exercise'] == target_ex].copy().sort_values('date')
    if len(sub_df) < 2: return jsonify({"error": "Data Kurang (Min 2 Sesi)"})

    # ML Prediction
    sub_df['date_ordinal'] = sub_df['date'].map(dt.datetime.toordinal)
    model = LinearRegression()
    model.fit(sub_df[['date_ordinal']], sub_df['e1rm'])
    
    # Predict Next Week & Month
    today = dt.date.today()
    future_dates = [today + dt.timedelta(days=i*7) for i in range(1, 5)]
    future_ordinal = [[d.toordinal()] for d in future_dates]
    future_preds = np.round(model.predict(future_ordinal)).astype(int)
    
    history_dates = sub_df['date'].dt.strftime('%Y-%m-%d').tolist()
    history_vals = np.round(sub_df['e1rm']).astype(int).tolist()
    future_dates_str = [d.strftime('%Y-%m-%d') for d in future_dates]
    
    current_pr = int(sub_df['e1rm'].max())
    target_pr = int(future_preds[0]) # Target Minggu Depan
    
    # Load Config BB buat hitung Rank
    cfg = load_config()
    
    return jsonify({
        "history": { "dates": history_dates, "values": history_vals },
        "prediction": { "dates": future_dates_str, "values": future_preds.tolist() },
        "current_pr": current_pr,
        "next_week_pr": target_pr,
        "rank": calculate_rank(target_ex, current_pr, cfg['bodyweight']),
        "recs": { "heavy": int(target_pr*0.85), "hyper": int(target_pr*0.75) }
    })

@app.route('/api/add', methods=['POST'])
def add_entry():
    global df
    data = request.json
    try:
        new_data = {
            'date': pd.to_datetime(data['date']),
            'exercise': data['exercise'],
            'weight': float(data['weight']),
            'reps': int(data['reps']),
            'set_type': 'NORMAL_SET',
            'volume': float(data['weight']) * int(data['reps']),
            'e1rm': round(float(data['weight']) * (1 + (int(data['reps']) / 30)), 2)
        }
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True).sort_values(by='date')
        
        # Simpan format string ke CSV
        df_save = df.copy()
        df_save.to_csv(CSV_FILE, index=False)
        
        return jsonify({"message": "Success", "new_pr": int(new_data['e1rm'])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)