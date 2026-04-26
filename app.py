from flask import Flask, redirect, request, session, jsonify
from flask_socketio import SocketIO
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import threading
import time
import syncedlyrics

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-read-currently-playing user-read-playback-state"
)

sp = None

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    global sp
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token'] = token_info
    sp = spotipy.Spotify(auth=token_info['access_token'])
    threading.Thread(target=poll_spotify, daemon=True).start()
    return redirect('/')

@app.route('/lyrics')
def get_lyrics():
    artist = request.args.get('artist', '')
    track = request.args.get('track', '')
    try:
        lrc = None

        # Intento 1: track + artist
        lrc = syncedlyrics.search(f"{track} {artist}")

        # Intento 2: solo el track
        if not lrc:
            lrc = syncedlyrics.search(track)

        # Intento 3: sin acentos
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

def poll_spotify():
    global sp
    while True:
        try:
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

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)