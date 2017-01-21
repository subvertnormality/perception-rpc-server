docker run -d -p 1935:1935 --name nginx-rtmp tiangolo/nginx-rtmp
docker start nginx-rtmp
START "" ngrok tcp -region eu --remote-addr 1.tcp.eu.ngrok.io:20245 50051
python control.py