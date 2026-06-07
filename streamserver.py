#!/usr/bin/python3

# StreamServer
# based on https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server_2.py
# (c) 2024 2025 axk339
# v0.1 - 05.10.2024 - MJPEG software encoding
# v0.3 - 05.11.2024 - MJPEG hardware encoding + RTSP/jpg
# v0.6 - 15.11.2024 - RTSP/jpg + high res snapshot
# v1.0 - 16.11.2024 - inital stable version
# v1.1 - 03.08.2025 - adding audio and metadata log plus performance improvement
# v1.2 - 07.10.2025 - adding lux control, improve overlay + logging, cleaning code from performance documentation
# v1.3 - 29.04.2026 - resolution optimization for camv3, error handlibg
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
from libcamera import controls, Transform

from threading import Thread, current_thread

import numpy as np
import cv2

import datetime

import time
import os.path
import math

#https://picamera.readthedocs.io/en/release-1.13/fov.html
#resx = 1640
#resy = 922
resx = 2304
resy = 1296
lowx = 1280
lowy = 720

logger = "/run/logger"
stream = "/run/streamserver"
delayTime = 60

camstat = "n/a"
PAGE_TEMPLATE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 Stream-Server</h1>
<p>Snapshot ({s_resx}x{s_resy})     <a href="snapshot.jpg">snapshot.jpg</a></p>
<p>Stream-Still ({s_lowx}x{s_lowy}) <a href="stream.jpg">stream.jpg</a></p>\
<p>Statistik:<br/>{s_camstat}</p> 
<p>Preview:</p>\
<img src="stream.jpg" width="{s_lowx}" height="{s_lowy}">\
</body>\
</html>
"""

class StreamingHandler(server.BaseHTTPRequestHandler):
    # Override log_message to do nothing
    def log_message(self, format, *args):
        return
    def do_GET(self):
        global log
        #log.info('Serving %s: %s', self.client_address, self.path)
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE_TEMPLATE.format(
                s_camstat=camstat, 
                s_resx=str(resx), 
                s_resy=str(resy), 
                s_lowx=str(lowx), 
                s_lowy=str(lowy)
            ).encode('utf-8')
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
                #frame  = picam2.capture_array("lores")
                #frame  = frame.astype(np.uint8)
                #rgb    = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                #frame2 = cv2.imencode(".jpg", rgb)[1].tobytes()
                buf = io.BytesIO()
                picam2.capture_file(buf, 'lores', format='jpeg')
                frame2 = buf.getvalue()
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame2))
                self.end_headers()
                self.wfile.write(frame2)
            except Exception as e:
                log.warning('Removed streaming client %s: %s', self.client_address, str(e))
        elif self.path == '/snapshot.jpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            try:
                #frame  = picam2.capture_array("main")
                #frame  = frame.astype(np.uint8)
                #rgb    = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                #frame2 = cv2.imencode(".jpg", rgb)[1].tobytes():
                buf = io.BytesIO()
                picam2.capture_file(buf, 'main', format='jpeg')
                frame2 = buf.getvalue()
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame2))
                self.end_headers()
                self.wfile.write(frame2)
            except Exception as e:
                log.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    
    # NEU: Diese Methode unterdrückt die Tracebacks bei Verbindungsabbrüchen
    def handle_error(self, request, client_address):
        import sys
        # Wir prüfen, ob es ein normaler Verbindungsabbruch ist
        cls, exc, tb = sys.exc_info()
        if cls is ConnectionResetError or cls is BrokenPipeError:
            # Einfach ignorieren, keine Log-Ausgabe
            log.info ("ConnectionReset " + str(client_address))
            return
        # Andere Fehler (echte Probleme) weiterhin loggen
        super().handle_error(request, client_address)

def serve():
    address = ('', 7123)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
    log.info ("Started HTTP Server on Port 7123")

# Logging to Journal
log = logging.getLogger("streamserver")
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='streamserver'))
log.setLevel(logging.INFO)
log.info('Started')

# Open PI Camera
picam2 = Picamera2()
config = picam2.create_video_configuration(
    main={"size": (resx, resy), "format": "YUV420"},
    lores={"size": (lowx, lowy), "format": "YUV420"},
    controls={
        #"AnalogueGain": 4,
        #"Brightness": 0.0,
        #"Contrast": 0.0,
        #"ExposureValue": 1.0,
        "AeExposureMode": controls.AeExposureModeEnum.Long,
        "FrameRate": 10,
        "AfMode": controls.AfModeEnum.Continuous,
        "AfMetering": controls.AfMeteringEnum.Auto,
        #"AfWindows": [focus_window],
        #"AfMode": controls.AfModeEnum.Manual,
        #"LensPosition": 0 #1.5 = Fokus 66cm > 0.5m - 5m scharf
        "AeMeteringMode": controls.AeMeteringModeEnum.Spot,
        "ExposureValue": 1.0  # Erhöht die Grundhelligkeit
    }
)
config["transform"] = Transform(hflip=True, vflip=True)
picam2.configure(config)

# Test overlay
colour = (255, 255, 255)
bg_colour = (128, 128, 128)   # Gray background
padding = 1
origin = (10, 20)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 0.5
thickness = 1
camstring = "AEmode=long, 10000 Lux"
# Get the size of the text
timestamp = "DoorCam " + time.strftime("%d.%m.%Y %X") + " (" + camstring + " plus extra)"
(text_width, text_height), baseline = cv2.getTextSize(timestamp, font, scale, thickness)
x1 = origin[0]
y1 = origin[1] - text_height - padding
x2 = origin[0] + text_width + padding
y2 = origin[1] + baseline + padding
def apply_timestamp(request):
    timestamp = "DoorCam " + time.strftime("%d.%m.%Y %X") + " (" + camstring + ")"
    with MappedArray(request, "lores") as m:
        cv2.rectangle(m.array, (x1, y1), (x2, y2), bg_colour, cv2.FILLED)
        cv2.putText(m.array, timestamp, origin, font, scale, colour, thickness)
picam2.pre_callback = apply_timestamp

# prepare ffmpeg command for streaming
#motion_atr_out = '-f rtsp rtsp://localhost:8554/cam_with_audio'
# Wir fügen rtpflags hinzu, um die Paketgröße zu begrenzen
#motion_atr_out = '-f rtsp -rtsp_transport udp -pkt_size 1300 rtsp://localhost:8554/cam_with_audio'
#encoder = H264Encoder (bitrate=1000000, iperiod=10, framerate=10)
motion_atr_out = '-f rtsp -rtsp_transport udp -pkt_size 1300 -thread_queue_size 1024 rtsp://localhost:8554/cam_with_audio'
#encoder = H264Encoder (bitrate=700000, iperiod=10, framerate=10)
encoder = H264Encoder (bitrate=1000000, iperiod=10, framerate=10)
#add alsa support:
#sudo nano /usr/lib/python3/dist-packages/picamera2/outputs/ffmpegoutput.py
#                           '-f', 'alsa,
#                         # '-f', 'pulse',
output = FfmpegOutput(
    motion_atr_out,
    audio=True,                         # Enable audio
    audio_device="default:CARD=Device", # Specify your ALSA device (adjust if "default" isn't correct)
    audio_samplerate=16000,             # Audio sample rate
    #audio_codec="libopus",             # Audio codec
    audio_codec="pcm_alaw",             # Audio codec
    audio_bitrate=64000                 # Audio bitrate in bps
)

# launch camera
picam2.start(show_preview=False)
picam2.start_encoder(encoder, output, name="lores")
log.info ("Started PiCam2")

# launch server non blocking (needs below: loop forever
thread = Thread(target=serve, args=( ))
thread.daemon = True
thread.start()

# create logger conf
confWritten = False
def loggerConf():
    global confWritten
    conf  = ";;doorpi_cam_temp;mean;none;°C;Grad Celsius\n"
    conf += ";;doorpi_cam_lux;mean;none;Lux;Lux\n"
    conf += ";;doorpi_cam_exposure;mean;none;;\n"
    conf += ";;doorpi_cam_analog_gain;mean;none;;\n"
    conf += ";;doorpi_cam_digital_gain;mean;none;;\n"
    conf += ";;doorpi_cam_color;mean;none;;\n"
    conf += ";;doorpi_cam_focus;mean;none;;\n"
    conf += ";;doorpi_cam_lens;mean;none;;\n"
    if os.path.isdir(logger):
        with open(logger + "/doorpi_cam.conf", "w") as f:
            f.write(conf)
        confWritten = True
loggerConf()

def calcTimerIntervall(secAlign):
    global delayTime
    targetIntervall = delayTime
    timestamp = datetime.datetime.now()
    timestampSec = (timestamp.second + timestamp.minute * 60) 
    curCount = math.floor(timestampSec / targetIntervall)
    nextIntervall = (curCount + 1) * targetIntervall - timestampSec
    nextIntervall += secAlign
    return nextIntervall

# loop forever
count = 60 # print log right away
lastMode = False
#if not os.path.exists(stream):
#    os.makedirs(stream)
try:
    while True:
        try:
            count += 1
            if count > 60:
                log.info("Serving...")
                count = 1
            cur = picam2.capture_metadata()
            #log.info("Serving... capture_metadata=" + str(cur))
            if confWritten:
                val  = ""
                if "SensorTemperature" in cur: val += "doorpi_cam_temp;" + str(cur["SensorTemperature"]) + ";;\n"
                val += "doorpi_cam_lux;" + str(cur["Lux"]) + ";;\n"
                val += "doorpi_cam_exposure;" + str(cur["ExposureTime"]/1000) + ";;\n"
                val += "doorpi_cam_analog_gain;" + str(cur["AnalogueGain"]) + ";;\n"
                val += "doorpi_cam_digital_gain;" + str(cur["DigitalGain"]) + ";;\n"
                val += "doorpi_cam_color;" + str(cur["ColourTemperature"]) + ";;\n"
                val += "doorpi_cam_focus;" + str(cur["FocusFoM"]) + ";;\n"
                val += "doorpi_cam_lens;" + str(cur["LensPosition"]) + ";;\n"
                with open(logger + "/doorpi_cam.log", "w") as f:
                    f.write(val)
                camstat = str(datetime.datetime.now()) + "<br/>\n"
                if "SensorTemperature" in cur: val += "Sensor Temp: " + str(cur["SensorTemperature"]) + "<br/>\n"
                camstat += "Lux: " + str(cur["Lux"]) + "<br/>\n"
                camstat += "Exposure: " + str(cur["ExposureTime"]/1000) + "<br/>\n"
                camstat += "Analog Gain: " + str(cur["AnalogueGain"]) + "<br/>\n"
                camstat += "Digital Gain: " + str(cur["DigitalGain"]) + "<br/>\n"
                camstat += "Color: " + str(cur["ColourTemperature"]) + "<br/>\n"
                camstat += "Focus: " + str(cur["FocusFoM"]) + "<br/>\n"
                camstat += "Lens: " + str(cur["LensPosition"]) + "<br/>\n"
            else:
                loggerConf()
            
            #not needed
            ##store frame every minute
            #frame = picam2.capture_array("main")
            #frame = frame.astype(np.uint8)
            #rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            #cv2.imwrite (stream+"/snapshot.jpg", rgb)
            
            #check / adjust exposure & gain
            if cur["Lux"] > 1000:
                picam2.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Short})
                if not lastMode:
                    lastMode = True
                    log.info("Changed AeExposureMode to short")
                camstring = "AEmode=short, " + str(math.floor(cur["Lux"])) + " Lux / AF " + str(cur["LensPosition"]) 
            else:
                picam2.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Long})
                if lastMode:
                    lastMode = False
                    log.info("Changed AeExposureMode to long")
                camstring = "AEmode=long, " + str(math.floor(cur["Lux"])) + " Lux / AF " + str(cur["LensPosition"]) 
            
        except Exception as e:
            log.warning("ERROR while processing main loop: " + str(e))
        
        time.sleep(calcTimerIntervall(10))
except Exception as e:
    log.info(str(e))
finally:
    picam2.stop_recording()
    log.info("Stopped PiCam2")


###Streaming Tests###

#>> finale Version: Python +overlay +300sec nosnap +hires mode 5 +stat // + Lux Test & Overlay

#08.10. (Python finale Version) Durchschnitt
#> CPU 14.7%, 46.2° / 47.2° max, 9.0W


