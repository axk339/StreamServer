#!/usr/bin/python3

# StreamServer
# based on https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server_2.py
# (c) 2024 axk339
# v0.1 - 05.10.2024 - MJPEG software encoding
# v0.3 - 05.11.2024 - MJPEG hardware encoding + RTSP

import io
import logging
from systemd.journal import JournalHandler

import socketserver
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import Encoder
from picamera2.encoders import H264Encoder
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from picamera2.outputs import FfmpegOutput

import datetime

import numpy as np
import cv2

resx       = 2304
resy       = 1296
lowx       = 1280
lowy       = 720
pathLog    = "/var/log/livecam/"

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 Stream-Server Demo</h1>
<p>Snapshot (4608x2592)    <a href="snapshot.jpg">snapshot.jpg</a></p>
<p>Stream-Still (1280x720) <a href="stream.jpg">stream.jpg</a></p>
<p>Preview:</p>
<img src="stream.jpg" width="1280" height="720" />
</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global clients3
        global clients2
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
        elif self.path == '/snapshot.jpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            clients2 += 1
            logger.info ("Now " + str(clients2) + " clients jpg")
            if clients2 == 1:
                logger.info ("Launching PiCam")
                picam2.start_encoder(encoder, FileOutput(output))               
            try:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
            except Exception as e:
                logger.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
            clients2 -= 1
            logger.info ("Now " + str(clients2) + " clients")
            if clients2 == 0:
                logger.info ("Stopping PiCam jpg")
                picam2.stop_encoder(encoders=encoder)
        elif self.path == '/stream.jpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            clients3 += 1
            logger.info ("Now " + str(clients2) + " clients jpg")
            if clients3 == 1:
                logger.info ("Launching PiCam")
                #picam2.start_encoder(encoder4, FileOutput(output), name="lores")               
            try:
                frame = picam2.capture_array("lores")
                frame = frame.astype(np.uint8)
                rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                frame2 = cv2.imencode(".jpg", rgb)[1].tobytes()
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame2))
                self.end_headers()
                self.wfile.write(frame2)
            except Exception as e:
                logger.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
            clients3 -= 1
            logger.info ("Now " + str(clients2) + " clients")
            if clients3 == 0:
                logger.info ("Stopping PiCam jpg")
                #picam2.stop_encoder(encoders=encoder)
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# Logging to Journal
logger = logging.getLogger(__name__)
logger.addHandler(JournalHandler())
logger.setLevel(logging.INFO)
logger.info('Started')

# Open PI Camera
picam2 = Picamera2()
config = picam2.create_video_configuration(
	main={"size": (resx, resy)},
	lores={"size": (lowx, lowy), "format": "YUV420"},
	controls={"FrameRate": 15}
#	controls={
#        ##"AnalogueGain": 8,
#        #"Brightness": 0.2,
#        #"Contrast": 1.2,
#        #"ExposureValue": 2.0,
#        #"AeExposureMode": 2
#    }
)
picam2.configure(config)

# start stream only when needed
output = StreamingOutput()
encoder = JpegEncoder()
encoder4 = Encoder()
clients = 0
clients2 = 0
clients3 = 0

# prepare ffmpeg command for streaming
motion_atr_out = '-f rtsp rtsp://localhost:8554/stream'
encoder2 = H264Encoder (bitrate=1000000)
#sudo apt-get install pulseaudio
#sudo apt-get install pulseaudio-utils
#output2 = FfmpegOutput (motion_atr_out, audio=True, audio_device="default:CARD=Device")
output2 = FfmpegOutput (motion_atr_out)
picam2.start_encoder(encoder2, output2, name="lores")
picam2.start()

try:
    address = ('', 7123)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()
