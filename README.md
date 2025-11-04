# StreamServer
RTSP/jpg + high res snapshot mediamtx script \
_This script provides a RTSP stream including a jpg still and a high resolution jpg snapshot on an integrated web server. The script can be launched directly within mediamtx, and published its RTSP stream via mediamtx._


# Prepare StreamServer script

__Dependencies__
~~~
sudo apt-get install python3-picamera2 python3-opencv ffmpeg python3-systemd
~~~

__Fix ALSA Support__ \
_By default, picamera2 only supports Pulse audio devices. For supporting ALSA audio devices, a fix in __ffmpegoutput.py__ is needed. This *fix needs to be re-applied after every apt-get upgrade!*_
~~~
sudo nano /usr/lib/python3/dist-packages/picamera2/outputs/ffmpegoutput.py
~~~

~~~
                         # '-f', 'pulse',
                           '-f', 'alsa,
~~~


# Install mediamtx

__Info__ \
https://github.com/bluenviron/mediamtx?tab=readme-ov-file#raspberry-pi-cameras

__Download__ \
https://github.com/bluenviron/mediamtx/releases \
*Tested:* mediamtx_v1.9.3_linux_arm64v8.tar.gz

_The server must run on a Raspberry Pi, with Raspberry Pi OS bullseye or newer as operative system. Both 32 bit and 64 bit operative systems are supported._

__Install__
~~~
sudo apt-get install libcamera0 libfreetype6
tar -xf mediamtx_v1.9.3_linux_arm64v8.tar.gz
sudo mv mediamtx /usr/local/bin/
sudo mv mediamtx.yml /usr/local/etc/
~~~

__Configuration__
~~~
sudo nano /usr/local/etc/mediamtx.yml
~~~

> rtspAddress: 0.0.0.0:8544 \
> rtmp: no \
> hls: no \
> webrtc: no \
> srt: no \

~~~
paths:
  cam_with_audio:
  stream:
    source: publisher
    runOnInit: python /home/pi/StreamServer/streamserver.py
    runOnInitRestart: yes
~~~

_Test_
~~~
sudo mediamtx
~~~
> rtsp://192.168.130.191:8554/stream

__Setup Service__
~~~
sudo nano /etc/systemd/system/mediamtx.service
~~~
_mediamtx.service_
~~~
[Unit]
Wants=network.target
[Service]
ExecStart=/usr/local/bin/mediamtx /usr/local/etc/mediamtx.yml
Restart=on-failure
Restart=always
RestartSec=50s
[Install]
WantedBy=multi-user.target
~~~

~~~
sudo systemctl daemon-reload
sudo systemctl enable mediamtx
sudo systemctl start mediamtx
sudo systemctl status mediamtx
~~~

_Check:_
~~~
sudo netstat -tulpn
~~~
  
