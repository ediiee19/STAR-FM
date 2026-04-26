const socket = io();

let lyrics = [];
let currentTrackId = null;

const trackName = document.getElementById('track-name');
const artistName = document.getElementById('artist-name');
const albumName = document.getElementById('album-name');
const coverImg = document.getElementById('cover-img');
const progress = document.getElementById('progress');
const curTime = document.getElementById('cur-time');
const totTime = document.getElementById('tot-time');
const lyricsContainer = document.getElementById('lyrics-container');
const statusText = document.getElementById('status-text');
const dotLive = document.querySelector('.dot-live');

function buildSpectrum() {
  const s = document.getElementById('spectrum');
  s.innerHTML = '';
  for (let i = 0; i < 24; i++) {
    const b = document.createElement('div');
    b.className = 'bar';
    const h = Math.floor(8 + Math.random() * 20);
    const d = (0.3 + Math.random() * 0.8).toFixed(2);
    b.style.cssText = `height:${h}px;--h:${Math.floor(18 + Math.random() * 16)}px;--d:${d}s;`;
    s.appendChild(b);
  }
}

buildSpectrum();

function formatTime(ms) {
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m + ':' + s.toString().padStart(2, '0');
}

function renderLyrics(progressMs) {
  if (!lyrics.length) return;

  let activeIndex = 0;
  for (let i = 0; i < lyrics.length; i++) {
    if (lyrics[i].time <= progressMs) {
      activeIndex = i;
    }
  }

  lyricsContainer.innerHTML = '';
  lyrics.forEach((line, i) => {
    const div = document.createElement('div');
    div.className = 'lyric-line';
    div.textContent = line.text;

    const diff = i - activeIndex;
    if (diff === 0) div.classList.add('active');
    else if (diff === 1 || diff === 2) div.classList.add('next');
    else if (diff < 0 && diff >= -2) div.classList.add('faint');
    else if (diff > 2) div.classList.add('faint');

    lyricsContainer.appendChild(div);
  });

  const activeLine = lyricsContainer.querySelector('.active');
  if (activeLine) {
    activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function fetchLyrics(artist, track) {
  try {
    const res = await fetch(`/lyrics?artist=${encodeURIComponent(artist)}&track=${encodeURIComponent(track)}`);
    const data = await res.json();
    lyrics = data.lyrics || [];
    if (!lyrics.length) {
      lyricsContainer.innerHTML = '<div class="lyric-line faint">Letras no disponibles</div>';
    }
  } catch (e) {
    lyricsContainer.innerHTML = '<div class="lyric-line faint">Error cargando letras</div>';
  }
}

socket.on('connect', () => {
  statusText.textContent = 'online';
  dotLive.classList.add('on');
});

socket.on('disconnect', () => {
  statusText.textContent = 'desconectado';
  dotLive.classList.remove('on');
});

socket.on('playback', (data) => {
  if (!data.is_playing) {
    statusText.textContent = 'pausado';
    dotLive.classList.remove('on');
    return;
  }

  statusText.textContent = 'online';
  dotLive.classList.add('on');

  trackName.textContent = data.track;
  artistName.textContent = data.artist;
  albumName.textContent = data.album;
  coverImg.src = data.cover;

  const pct = (data.progress_ms / data.duration_ms) * 100;
  progress.style.width = pct + '%';
  curTime.textContent = formatTime(data.progress_ms);
  totTime.textContent = formatTime(data.duration_ms);

  if (data.track_id !== currentTrackId) {
    currentTrackId = data.track_id;
    lyrics = [];
    lyricsContainer.innerHTML = '<div class="lyric-line faint">Cargando letras...</div>';
    fetchLyrics(data.artist, data.track);
  }

  renderLyrics(data.progress_ms + 450);
});