#!/usr/bin/python3

# StreamServer
# based on https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server_2.py
# (c) 2024 axk339
# v0.1 - 05.10.2024 - MJPEG software encoding
# v0.3 - 05.11.2024 - MJPEG hardware encoding + RTSP/jpg
# v0.6 - 15.11.2024 - RTSP/jpg + high res snapshot
# v1.0 - 16.11.2024 - inital stable version
# v1.1 - 03.08.2025 - adding audio plus performance improvement
# v1.2 - xx.08.2025 - cleaning code from performance documentation

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
from libcamera import controls

from threading import Thread, current_thread

import numpy as np
import cv2
#from PIL import Image, ImageDraw, ImageFont

import datetime
import time
import os.path
import math

#https://picamera.readthedocs.io/en/release-1.13/fov.html
#v1.1 optmize res to sensor modes, but keep lores
#resx       = 2593
#resy       = 
resx       = 1640
resy       = 922
#v1.1 higher hires, +3% CPU
#resx       = 2592
#resy       = 1944
#v1.1 optmize res to sensor modes > better viewfield, + 0 2% CPU
#lowx      = 1280
#lowy      = 720
#lowx       = 1640
#lowy       = 922
lowx      = 1280
lowy      = 720
# max res für pi3 cma > grep Cma /proc/meminfo
# andere Raten (auch niedrigere) viel höhere CPU Usage

logger = "/run/logger"
delayTime = 60

PAGE = """\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 Stream-Server</h1>
<p>Snapshot ({s_resx}x{s_resy})     <a href="snapshot.jpg">snapshot.jpg</a></p>
<p>Stream-Still ({s_lowx}x{s_lowy}) <a href="stream.jpg">stream.jpg</a></p>\
<p>Preview:</p>\
<img src="stream.jpg" width="{s_lowx}" height="{s_lowy}">\
</body>\
</html>
""".format(s_resx=str(resx), s_resy=str(resy), s_lowx=str(lowx), s_lowy=str(lowy))

class StreamingHandler(server.BaseHTTPRequestHandler):
    # Override log_message to do nothing
    def log_message(self, format, *args):
        return
    def do_GET(self):
        global log
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
                log.warning('Removed streaming client %s: %s', self.client_address, str(e))
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
                log.warning('Removed streaming client %s: %s', self.client_address, str(e))
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
    log.info ("Started HTTP Server on Port 7123")

# Logging to Journal
log = logging.getLogger("streamserver")
log.addHandler(JournalHandler(SYSLOG_IDENTIFIER='streamserver'))
log.setLevel(logging.INFO)
log.info('Started')

# Open PI Camera
picam2 = Picamera2()
#only for info
#for n, m in enumerate(picam2.sensor_modes):
#    log.info ("Mode" + str(n) + ":" + str(m))
#props = picam2.camera_properties
#log.info ("Camera Properties:" + str(props))
config = picam2.create_video_configuration(
    #v1.1 reduce main strain res, ~5% CPU
    #main={"size": (resx, resy), "format": "YUV420"},
    #main={"size": (lowx, lowy), "format": "YUV420"},
    #v1.1 back to hires but optimized
    main={"size": (resx, resy), "format": "YUV420"},
    #v1.1 keep lores stream even if same res, ~2% CPU
    lores={"size": (lowx, lowy), "format": "YUV420"},
    controls={
        #"AnalogueGain": 2,
        "Brightness": 0.2,
        "Contrast": 1.2,
        #"ExposureValue": 1.0,
        "AeExposureMode": controls.AeExposureModeEnum.Long,
        "FrameRate": 10,
        "AfMode": controls.AfModeEnum.Continuous
    }
);
picam2.configure(config)

# Test overlay
#v1.1 text overlay ~2% CPU
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

# Define the font and size you want to use.
# You will need to provide a path to a .ttf file.
# Replace 'path/to/your/font.ttf' with the actual path to your font file.
#try:
#    font = ImageFont.truetype("/home/pi/StreamingServer/editunline.ttf", 18)
#except IOError:
#    print("Could not load the font. Using default.")
#    font = ImageFont.load_default() # Fallback to a default font

def apply_monochrome_overlay2(request):
    with MappedArray(request, "lores") as m:
        yuv_array = m.array
        array_height, array_width = m.array.shape[:2]
        y_plane_size = array_width * array_height
        # Create a view of the Y plane data, reshaped to 2D.
        y_plane_view = yuv_array[:y_plane_size].reshape((array_height, array_width))
        # We can also avoid `Image.fromarray` and `np.array` by modifying a `frombuffer` image.
        pil_image_y = Image.frombuffer('L', (array_width, array_height), y_plane_view)
        
        # Create a drawing context for the Pillow image.
        draw = ImageDraw.Draw(pil_image_y)
        # Define the text string and its properties.
        timestamp_text = "DoorCam " + time.strftime("%d.%m.%Y %X")
        text_position = (10, 10)
        text_color = 255
        # Draw the text onto the Pillow image representing the Y-plane.
        draw.text(text_position, timestamp_text, fill=text_color, font=font)
        
        # Note: In-place modification of the `frombuffer` image directly
        # modifies the `y_plane_view` array, so no write-back is needed.
        # The buffer is already updated.

def apply_monochrome_overlay(request):
    with MappedArray(request, "lores") as m:
        yuv_array = m.array
        array_height, array_width = m.array.shape[:2]
        y_plane_size = array_width * array_height
        # Create a view of the Y plane data, reshaped to 2D.
        y_plane_view = yuv_array[:y_plane_size].reshape((array_height, array_width))
        # Convert the Y plane (which is 8-bit grayscale) to a Pillow Image.
        pil_image_y = Image.fromarray(y_plane_view, 'L')
        
        # Create a drawing context for the Pillow image.
        draw = ImageDraw.Draw(pil_image_y)
        # Define the text string and its properties.
        timestamp_text = "DoorCam " + time.strftime("%d.%m.%Y %X")
        text_position = (10, 10)
        text_color = 255  # White
        # Draw the text onto the Pillow image representing the Y-plane.
        draw.text(text_position, timestamp_text, fill=text_color, font=font)
        
        # Convert the modified Pillow image back to a NumPy array.
        # This creates a new array, which is the source of the overhead but
        # also the reason for reliability.
        modified_y_plane = np.array(pil_image_y)
        # Write the modified Y-plane data back into the original YUV buffer.
        # We ensure the shapes match exactly before the assignment.
        yuv_array[:] = modified_y_plane

# Assign our overlay function as the pre_callback.
#ca 6% cpu usage
#picam2.pre_callback = apply_monochrome_overlay
#minimal cpi usage but no overlay applied
#picam2.pre_callback = apply_monochrome_overlay2

# prepare ffmpeg command for streaming
motion_atr_out = '-f rtsp rtsp://localhost:8554/cam_with_audio'
#iperiod=15 > keyframe every second, ~1-2% CPU
encoder = H264Encoder (bitrate=1000000, iperiod=10, framerate=10)
#encoder = H264Encoder (bitrate=300000, iperiod=10, framerate=10)
#add alsa support:
#sudo nano /usr/lib/python3/dist-packages/picamera2/outputs/ffmpegoutput.py
#                           '-f', 'alsa,
#                         # '-f', 'pulse',
output = FfmpegOutput(
    motion_atr_out,
    audio=True,                         # Enable audio
    audio_device="default:CARD=Device", # Specify your ALSA device (adjust if "default" isn't correct)
    audio_samplerate=16000,             # Audio sample rate
    audio_codec="libopus",              # Audio codec
    audio_bitrate=64000                 # Audio bitrate in bps
    #audio_bitrate=16000                # Audio bitrate in bps
)

# launch camera
picam2.start(show_preview=False)
picam2.start_encoder(encoder, output, name="lores")
log.info ("Started PiCam2")

# launch server non blocking (needs below: loop forever
thread = Thread(target=serve, args=( ))
#thread.setDaemon(True)
thread.daemon = True
thread.start()

# launch server blocking
# v1.1 0% CPU impact
#serve()
#picam2.stop_recording()
#log.info("Stopped PiCam2")

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
    #if nextIntervall > (delayTime - secAlign):
    #    nextIntervall -= (delayTime - secAlign)
    #else:
    #    nextIntervall += (secAlign)
    nextIntervall += secAlign
    return nextIntervall

# loop forever
try:
    while True:
        try:
            cur = picam2.capture_metadata()
            log.info("Serving...")
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
            else:
                loggerConf()
            
            #store frame every minute
            #v1.1 0.5% CPU if storing snapshot
            #frame = picam2.capture_array("lores")
            #frame = frame.astype(np.uint8)
            #rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            #cv2.imwrite ("/run/streamserver/stream.jpg", rgb)
            #log.info("Wrote stream.jpg")
            
            #check / adjust exposure & gain
            #based on time/sunset or based lightness sensor (?) or based on image content
            #...todo...
            
        except Exception as e:
            log.warning("ERROR while processing main loop: " + str(e))
        
        #v1.1 no difference if sleep 60 or 3600
        time.sleep(calcTimerIntervall(10))
        #time.sleep(3600)
except Exception as e:
    log.info(str(e))
finally:
    picam2.stop_recording()
    log.info("Stopped PiCam2")


###Streaming Tests###

#18.07. (Python alte Version) Durchsch. Tag
#> CPU 23.2%, 53.9° / 55.8° max, 10.6W

#20.07. (Python neu) aktueller Wert
#> CPU 18%, 48°, 9W

#21.07. (Python neu) Durchsch. Tag
#> CPU 17.6%, 48.5° / 49.9° max, 8.8W

#22.07. (Libcamera-vid) aktueller Wert
#> CPU 13%, 50°, 9W

#23.07. (Libcamera-vid) Durchsch. Tag
#> CPU 13.2%, 49.1° / 50.5° max, 8.7W

#26.07. (Python 2nd stream + overlay) Durchschnitt 10h
#> CPU 17.2%, 48.6° / 49.4° max, 8.8W

#26.07. (Python 2nd stream ohne overlay) Durchschnitt 1h
#> CPU 15%, 48.7°, 8.8W

#26.07. (Python 10 FPS but keyframe 1s) Durchschnitt 1h
#> CPU 13%, 47.2°, 8.5W

#27.07. (Python bitrate 1m/64k) Durchschnitt 10h
#> CPU 13.5%, 47.6° / 48.2° max, 8.5W

#28.07. (Python bitrate 1m/64k) Durchschnitt
#> CPU 13.5%, 47.2° / 48.3° max, 8.5W

#30.07. (Python +overlay) Durchschnitt
#> CPU 14.0%, 46.5° / 48.3° max, 8.6W                     << REFERENCE

#01.08. (Python +overlay +hires snapshot) Durchschnitt
#> CPU 17.4%, 49.4° / 50.5° max, 9.7W

#02.08. (Python +overlay +60s snapshot) Durchschnitt 1h
#> CPU 14.4%, 45.0°, 8.5W

#03.08. (Python +overlay +60s no snap) Durchschnitt 1h
#> CPU 13.9%, 45.7°, 8.5W

#03.08. (Python +overlay +blocking server) Durchschnitt 1h
#> CPU 13.9%, 46.4°, 8.5W

#07.08. (Python +hires mode 5) Durchschnitt 1h
#> CPU 14.1%, 47.4°, 9.0W

#08.08. (Python +hires mode 5 +stat) Durchschnitt 1h
#> CPU 14.2%, 47.1°, 8.8W

#21.08. (Python +higher hires) Durchschnitt 1h
#> CPU 17.4%, 50.8°, 9.7W

#21.08. (Python +hires mode 5 +stat) Durchschnitt 1h
#> CPU 14.8%, 46.3°, 8.6W

#>> finale Version: Python +overlay +300sec nosnap +hires mode 5 +stat // + Lux Test & Overlay

#23.08. (Python finale Version) Durchschnitt
#> CPU 14.7%, 46.6° / 48.3° max, 8.7W

#24.08. (Python finale Version) Durchschnitt
#> CPU 14.7%, 47.1° / 48.3° max, 8.8W

#07.10. (Python finale Version with snapshot) Durchschnitt 1h
#> CPU 14.8%, 45.2°, 9.0W

#07.10. (Python finale Version without snapshot) Durchschnitt 1h
#> CPU 14.8%, 46.2°, 9.0W

#>> finale Version: Python +overlay +300sec nosnap +hires mode 5 +stat // + Lux Test & Overlay // mit oder ohne Snapshot

#08.10. (Python finale Version) Durchschnitt
#> CPU 14.7%, 46.2° / 47.2° max, 9.0W


