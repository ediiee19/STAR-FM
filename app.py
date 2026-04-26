from flask import Flask, redirect, request, session, jsonify
from flask_socketio import SocketIO
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import threading
import time
import syncedlyrics
import json

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'starfm-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*")

TOKEN_FILE = '.spotify_token'

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-currently-playing user-read-playback-state user-modify-playback-state"
)

sp = None
polling_started = False

def save_token(token_info):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_info, f)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            return json.load(f)
    return None

def get_spotify():
    global sp
    token_info = load_token()
    if not token_info:
        return None
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        save_token(token_info)
    sp = spotipy.Spotify(auth=token_info['access_token'])
    return sp

@app.route('/')
def index():
    token_info = load_token()
    if not token_info:
        return redirect('/login')
    return app.send_static_file('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    global polling_started
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    save_token(token_info)
    get_spotify()
    if not polling_started:
        polling_started = True
        threading.Thread(target=poll_spotify, daemon=True).start()
    return redirect('/')

@app.route('/lyrics')
def get_lyrics():
    artist = request.args.get('artist', '')
    track = request.args.get('track', '')
    try:
        lrc = None
        lrc = syncedlyrics.search(f"{track} {artist}")
        if not lrc:
            lrc = syncedlyrics.search(track)
        if not lrc:
            import unicodedata
            def quitar_acentos(texto):
                return ''.join(c for c in unicodedata.normalize('NFD', texto)
                               if unicodedata.category(c) != 'Mn')
            lrc = syncedlyrics.search(f"{quitar_acentos(track)} {quitar_acentos(artist)}")
        if not lrc:
            return jsonify({'lyrics': []})
        parsed = []
        for line in lrc.strip().split('\n'):
            if line.startswith('[') and ']' in line:
                try:
                    time_str = line[1:line.index(']')]
                    text = line[line.index(']')+1:].strip()
                    if ':' in time_str and text:
                        parts = time_str.split(':')
                        minutes = float(parts[0])
                        seconds = float(parts[1])
                        ms = int((minutes * 60 + seconds) * 1000)
                        parsed.append({'time': ms, 'text': text})
                except:
                    continue
        return jsonify({'lyrics': parsed})
    except Exception as e:
        print(f"Error letras: {e}")
        return jsonify({'lyrics': []})

@app.route('/next')
def next_track():
    try:
        get_spotify()
        sp.next_track()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/prev')
def prev_track():
    try:
        get_spotify()
        sp.previous_track()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/pause')
def pause_track():
    try:
        get_spotify()
        playback = sp.current_playback()
        if playback and playback['is_playing']:
            sp.pause_playback()
        else:
            sp.start_playback()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

def poll_spotify():
    global sp
    while True:
        try:
            get_spotify()
            if sp:
                playback = sp.current_playback()
                if playback and playback['is_playing']:
                    track = playback['item']
                    data = {
                        'track': track['name'],
                        'artist': track['artists'][0]['name'],
                        'album': track['album']['name'],
                        'cover': track['album']['images'][0]['url'],
                        'track_id': track['id'],
                        'progress_ms': playback['progress_ms'],
                        'duration_ms': track['duration_ms'],
                        'is_playing': True
                    }
                    socketio.emit('playback', data)
                else:
                    socketio.emit('playback', {'is_playing': False})
        except Exception as e:
            print(f"Error polling: {e}")
        time.sleep(1)

# Arrancar polling si ya hay token guardado
token_info = load_token()
if token_info:
    get_spotify()
    polling_started = True
    threading.Thread(target=poll_spotify, daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)