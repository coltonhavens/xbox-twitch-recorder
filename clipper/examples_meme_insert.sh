# Meme insert used in the Nov 26 test. usage: meme SRC_CLIP OVERLAY_DIR SOUND DUR OUT
# OVERLAY_DIR = 1280x720 PNG frames (avatar pop-in + text) made with PIL, see RUNBOOK "Meme reactions".
meme(){ ffmpeg -v error -y -sseof -0.05 -i "$1" -frames:v 1 last.png
  ffmpeg -v error -y -loop 1 -t "$4" -i last.png -framerate 30 -i "$2"/%03d.png -i "$3" -filter_complex "[0:v]scale=1280:720,eq=brightness=-0.18:saturation=0.6,boxblur=6:1[bg];[bg][1:v]overlay=0:0:shortest=1,setsar=1,fps=30[v];[2:a]apad,atrim=0:$4,aresample=48000[a]" -map "[v]" -map "[a]" -t "$4" -c:v libx264 -preset veryfast -crf 16 -r 30 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2 "$5"; }
