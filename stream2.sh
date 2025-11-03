#!/bin/bash

rpicam-vid -t 0 \
--inline --width 1280 --height 720 --framerate 15 --nopreview --bitrate 300000 -o - | \

#libcamera-vid -t 0 \
#--inline --width 1280 --height 720 --framerate 15 --nopreview --bitrate 800000 -o - | \

###v2
ffmpeg \
-i - \
-f alsa -ac 1 -ar 8000 -guess_layout_max 0 -channel_layout mono -i default:CARD=Device \
-c:v copy -c:a libopus -b:a 64k -ac 1 \
-fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 -tune zerolatency \
-f rtsp rtsp://localhost:8554/cam_with_audio
#-f mp4 test.mp4

###v1
#ffmpeg -i - -f alsa -ac 1 -ar 44100 -itsoffset 0.0 -channel_layout mono -i default:CARD=Device \
#-map 0:v:0 -map 1:a:0 -c:v copy -c:a libopus -b:a 64k \
#-fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0 -tune zerolatency \
#-f rtsp rtsp://localhost:8554/cam_with_audio



###helper
# nohup /home/pi/StreamServer/stream2.sh &
# ps -aux | grep stream
# kill -SIGTERM -- -PID

