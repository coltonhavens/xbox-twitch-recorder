"""Explicit owner-VOD compatibility test. No cloud/Drive access and no upload."""
import argparse
import json
from pathlib import Path
import subprocess
from .worker import CHANNEL, mux_args, stage_video, validate_info, vod_info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vod-id', default='2917078189')
    parser.add_argument('--output', type=Path, help='Optional full download to a local file; reserve enough disk')
    args = parser.parse_args()
    info = vod_info(args.vod_id)
    if str(info.get('uploader_id', '')).lower() != CHANNEL:
        raise SystemExit('VOD is not owned by MrHype420')
    duration = int(info.get('duration') or 0)
    video = {'id': args.vod_id, 'duration': f'{duration}s'}
    validate_info(info, video)
    print(json.dumps({'vod_id': args.vod_id, 'channel': CHANNEL, 'duration_seconds': duration,
                      'completed': info['is_live'] is False, 'downloaded': False}))
    if args.output:
        with args.output.open('xb') as sink:
            metadata = stage_video(video, sink)
        result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type:format=duration',
                                 '-of', 'json', str(args.output)], capture_output=True, timeout=300, check=True)
        probe = json.loads(result.stdout)
        if not {'audio', 'video'}.issubset({s['codec_type'] for s in probe.get('streams', [])}):
            raise ValueError('Missing audio/video')
        print(json.dumps(dict(metadata, downloaded=True, audio_video_tracks=True)))
        # Listening is still required to verify microphone speech, not just an audio track.


if __name__ == '__main__':
    main()
