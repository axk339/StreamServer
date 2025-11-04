# StreamServer
RTSP/jpg + high res snapshot mediamtx script


# Install mediamtx

__Info__
https://github.com/bluenviron/mediamtx?tab=readme-ov-file#raspberry-pi-cameras

__Download__
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
> \
> paths: \
>   cam_with_audio: \
>   stream: \
>     source: publisher \
>     runOnInit: python /home/pi/StreamServer/streamserver.py \
>     runOnInitRestart: yes \

_Test_
sudo mediamtx
> rtsp://192.168.130.191:8554/stream
