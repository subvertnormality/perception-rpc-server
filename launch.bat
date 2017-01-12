C:\Program Files\MongoDB\Server\3.4\bin\mongod.exe
docker run -d -p 1935:1935 --name nginx-rtmp tiangolo/nginx-rtmp
docker start nginx-rtmp
START "" ngrok tcp -region eu --remote-addr 1.tcp.eu.ngrok.io:20187 50051
python control.py