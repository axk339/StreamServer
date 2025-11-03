#!/usr/bin/python3

# StreamServer
# based on https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server_2.py
# (c) 2024 axk339
# v0.1 - 05.10.2024 - MJPEG software encoding
# v0.3 - 05.11.2024 - MJPEG hardware encoding + RTSP/jpg
# v0.6 - 15.11.2024 - RTSP/jpg + high res snapshot
# v1.0 - 16.11.2024 - inital stable version

import io
import logging
from systemd.journal import JournalHandler

import socketserver
from http import server
from threading import Condition

from picamera2 import MappedArray, Picamera2
from picamera2.encoders import Encoder
from picamera2.encoders import H264Encoder
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from picamera2.outputs import FfmpegOutput

import datetime
import time

import numpy as np
import cv2

from threading import Thread, current_thread

resx       = 2593
resy       = 1944
lowx       = 1280
lowy       = 720
# max res für pi3 cma > grep Cma /proc/meminfo
# andere Raten (auch niedrigere) viel höhere CPU Usage

pathLog    = "/var/log/livecam/"

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 Stream-Server Demo</h1>
<p>Snapshot (2593x1944)    <a href="snapshot.jpg">snapshot.jpg</a></p>
<p>Stream-Still (1280x720) <a href="stream.jpg">stream.jpg</a></p>
<p>Preview:</p>
<img src="stream.jpg" width="1280" height="720" />
</body>
</html>
"""

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global logger
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.jpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            try:
                frame  = picam2.capture_array("lores")
                frame  = frame.astype(np.uint8)
                rgb    = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                frame2 = cv2.imencode(".jpg", rgb)[1].tobytes()
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame2))
                self.end_headers()
                self.wfile.write(frame2)
            except Exception as e:
                logger.warning('Removed streaming client %s: %s', self.client_address, str(e))
        elif self.path == '/snapshot.jpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            try:
                frame  = picam2.capture_array("main")
                frame  = frame.astype(np.uint8)
                rgb    = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                frame2 = cv2.imencode(".jpg", rgb)[1].tobytes()
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame2))
                self.end_headers()
                self.wfile.write(frame2)
            except Exception as e:
                logger.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def serve():
    address = ('', 7123)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
    logger.info ("Started HTTP Server on Port 7123")

# Logging to Journal
logger = logging.getLogger("streamserver")
logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER='streamserver'))
logger.setLevel(logging.INFO)
logger.info('Started')

# Open PI Camera
picam2 = Picamera2()
config = picam2.create_video_configuration(
	main={"size": (resx, resy), "format": "YUV420"},
	lores={"size": (lowx, lowy), "format": "YUV420"},
	controls={
	    "AnalogueGain": 4,
        "Brightness": 0.2,
        "Contrast": 1.2,
        "ExposureValue": 2.0,
        "AeExposureMode": 2
    }
);

picam2.configure(config)

# Test overlay
colour = (255, 255, 255)
origin = (10, 20)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 0.5
thickness = 1
def apply_timestamp(request):
    timestamp = "DoorCam " + time.strftime("%d.%m.%Y %X")
    with MappedArray(request, "lores") as m:
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
picam2.pre_callback = apply_timestamp

# prepare ffmpeg command for streaming
motion_atr_out = '-f rtsp rtsp://localhost:8554/stream'
encoder = H264Encoder (bitrate=1000000)
output  = FfmpegOutput (motion_atr_out)
picam2.start_encoder(encoder, output, name="lores")

# launch
picam2.start()
logger.info ("Started PiCam2")
thread = Thread(target=serve, args=( ))
thread.setDaemon(True)
thread.start()

# loop forever
try:
    while True:
        logger.info("Serving...")
        try:
            #store frame every minute
            frame = picam2.capture_array("lores")
            frame = frame.astype(np.uint8)
            rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            cv2.imwrite ("/run/streamserver/stream.jpg", rgb)
            logger.info("Wrote stream.jpg")
            
            #check / adjust exposure & gain
            ##todo..
            
        except Exception as e:
            logger.warning("ERROR while storing stream.jpg: " + str(e))
        time.sleep(60)
except Exception as e:
    logger.info(str(e))
finally:
    picam2.stop_recording()
    logger.info("Stopped PiCam2")
