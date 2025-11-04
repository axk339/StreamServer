# Resolution

~~~
#https://picamera.readthedocs.io/en/release-1.13/fov.html
#v1.1 optmize res to sensor modes, but keep lores
#resx       = 2593
#resy       = 
resx       = 1640
resy       = 922
#v1.1 higher hires, +3% CPU
#resx       = 2592
#resy       = 1944
#v1.1 optmize res to sensor modes > better viewfield, +2% CPU
#lowx      = 1280
#lowy      = 720
#lowx       = 1640
#lowy       = 922
lowx      = 1280
lowy      = 720
# max res für pi3 cma > grep Cma /proc/meminfo
# andere Raten (auch niedrigere) viel höhere CPU Usage
~~~

# Secondary stream

~~~
config = picam2.create_video_configuration(
    #v1.1 reduce main strain res, ~5% CPU
    #main={"size": (resx, resy), "format": "YUV420"},
    #main={"size": (lowx, lowy), "format": "YUV420"},
    #v1.1 back to hires but optimized
    main={"size": (resx, resy), "format": "YUV420"},
    #v1.1 keep lores stream even if same res, ~2% CPU
    lores={"size": (lowx, lowy), "format": "YUV420"},
);
~~~

# Text Overlay 

~~~
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
~~~

# Alternative Overlay

~~~
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
~~~

# Blocking server
_Avoids further code in endless loop._

~~~
# launch server blocking
# v1.1 0% CPU impact
#serve()
#picam2.stop_recording()
#log.info("Stopped PiCam2")
~~~

# Store frame

~~~
            #store frame every minute
            #v1.1 0.5% CPU if storing snapshot
            #frame = picam2.capture_array("lores")
            #frame = frame.astype(np.uint8)
            #rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            #cv2.imwrite ("/run/streamserver/stream.jpg", rgb)
            #log.info("Wrote stream.jpg")
~~~

# Sleep

~~~
        #v1.1 no difference if sleep 60 or 3600
        time.sleep(calcTimerIntervall(10))
        #time.sleep(3600)
~~~


# Streaming Tests

18.07. (Python alte Version) Durchsch. Tag
> CPU 23.2%, 53.9° / 55.8° max, 10.6W

20.07. (Python neu) aktueller Wert
> CPU 18%, 48°, 9W

21.07. (Python neu) Durchsch. Tag
> CPU 17.6%, 48.5° / 49.9° max, 8.8W

22.07. (Libcamera-vid) aktueller Wert
> CPU 13%, 50°, 9W

23.07. (Libcamera-vid) Durchsch. Tag
> CPU 13.2%, 49.1° / 50.5° max, 8.7W

26.07. (Python 2nd stream + overlay) Durchschnitt 10h
> CPU 17.2%, 48.6° / 49.4° max, 8.8W

26.07. (Python 2nd stream ohne overlay) Durchschnitt 1h
> CPU 15%, 48.7°, 8.8W

26.07. (Python 10 FPS but keyframe 1s) Durchschnitt 1h
> CPU 13%, 47.2°, 8.5W

27.07. (Python bitrate 1m/64k) Durchschnitt 10h
> CPU 13.5%, 47.6° / 48.2° max, 8.5W

28.07. (Python bitrate 1m/64k) Durchschnitt
> CPU 13.5%, 47.2° / 48.3° max, 8.5W

30.07. (Python +overlay) Durchschnitt
> CPU 14.0%, 46.5° / 48.3° max, 8.6W                     << REFERENCE

01.08. (Python +overlay +hires snapshot) Durchschnitt
> CPU 17.4%, 49.4° / 50.5° max, 9.7W

02.08. (Python +overlay +60s snapshot) Durchschnitt 1h
> CPU 14.4%, 45.0°, 8.5W

03.08. (Python +overlay +60s no snap) Durchschnitt 1h
> CPU 13.9%, 45.7°, 8.5W

03.08. (Python +overlay +blocking server) Durchschnitt 1h
> CPU 13.9%, 46.4°, 8.5W

07.08. (Python +hires mode 5) Durchschnitt 1h
> CPU 14.1%, 47.4°, 9.0W

08.08. (Python +hires mode 5 +stat) Durchschnitt 1h
> CPU 14.2%, 47.1°, 8.8W

21.08. (Python +higher hires) Durchschnitt 1h
> CPU 17.4%, 50.8°, 9.7W

21.08. (Python +hires mode 5 +stat) Durchschnitt 1h
> CPU 14.8%, 46.3°, 8.6W

>> finale Version: Python +overlay +300sec nosnap +hires mode 5 +stat // + Lux Test & Overlay

23.08. (Python finale Version) Durchschnitt
> CPU 14.7%, 46.6° / 48.3° max, 8.7W

24.08. (Python finale Version) Durchschnitt
> CPU 14.7%, 47.1° / 48.3° max, 8.8W

07.10. (Python finale Version with snapshot) Durchschnitt 1h
> CPU 14.8%, 45.2°, 9.0W

07.10. (Python finale Version without snapshot) Durchschnitt 1h
> CPU 14.8%, 46.2°, 9.0W

>> finale Version: Python +overlay +300sec nosnap +hires mode 5 +stat // + Lux Test & Overlay // mit oder ohne Snapshot

08.10. (Python finale Version) Durchschnitt
> CPU 14.7%, 46.2° / 47.2° max, 9.0W

