# LAN Audio Hub Setup

## 1) Server laptop

Run on the laptop that stores shared audio files:

```bash
cd /Users/macbook/musicAPP
pip install -r lan_audio_hub/requirements-lan.txt
python -m lan_audio_hub
```

By default hub starts at `0.0.0.0:8765`.

## 2) Find server LAN IP

On server laptop:

```bash
ipconfig getifaddr en0
```

Example result: `192.168.0.154`

## 3) Verify from client laptop

Use server IP, not localhost:

```bash
curl -s http://192.168.0.154:8765/health
curl -s http://192.168.0.154:8765/tracks
```

Expected health response: `{"ok":true}`.

## 4) Configure Django backend

On the machine where Django backend runs, set LAN hub URL:

```bash
export CRATES_LAN_HUB_URL=http://192.168.0.154:8765
```

This value is used by Django endpoint `POST /api/music-items/upload-via-lan/`:
- the desktop client uploads the selected local file to Django;
- Django forwards the file to LAN Audio Hub;
- Django creates `MusicItem(provider="lan_hub")`;
- playback later uses only server `audio_url`, so local source file may be deleted.

## 5) Optional direct upload to hub (manual test only)

```bash
curl -X POST http://192.168.0.154:8765/upload \
  -F "file=@/absolute/path/to/track.mp3" \
  -F "title=Track title" \
  -F "artist=Artist name"
```

## 6) Configure CRATES client app

Set LAN hub URL before starting app:

```bash
export CRATES_LAN_HUB_URL=http://192.168.0.154:8765
python main.py
```

Then upload a track from the app UI. The track will be stored on the server and returned by normal `/api/music-items/` search as a regular catalog item.

## Notes

- `127.0.0.1` works only on the same machine where server runs.
- Client must use real server LAN IP (`192.168.x.x` etc.).
- If connection fails, check firewall and that both laptops are in the same network.
- After successful upload the original local file on the client is no longer required for playback.
