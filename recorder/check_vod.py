"""Explicit no-upload compatibility test for the owner's VOD."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from .worker import Video, metadata, CHUNK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vod-id', default='2917078189')
    parser.add_argument('--output', type=Path, help='Optional local full-file test; not production storage')
    args = parser.parse_args()
    try:
        video = metadata(args.vod_id)
        print(json.dumps(dict(video, completed=True, downloaded=False)))
        if args.output:
            # This optional local test needs full disk; the Actions archive uses a pipe instead.
            with args.output.open('xb') as output, Video(video) as reader:
                while block := reader.read(CHUNK):
                    if shutil.disk_usage(args.output.parent).free < 1024**3:
                        raise RuntimeError('Insufficient test disk; stop before filling it')
                    output.write(block)
                reader.finish()
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type:format=duration',
                                     '-of', 'json', str(args.output)], capture_output=True, check=True, timeout=300)
            info = json.loads(result.stdout)
            if not {'audio', 'video'}.issubset({stream['codec_type'] for stream in info.get('streams', [])}):
                raise ValueError('Missing video or audio')
            print(json.dumps({'downloaded': True, 'audio_video_tracks': True, 'vod_id': args.vod_id}))
    except Exception as exc:
        # Never print yt-dlp exceptions containing playback URLs or response bodies.
        print(json.dumps({'vod_id': args.vod_id, 'success': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
