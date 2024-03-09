

docker build -t odinluo/img2oss .
docker push odinluo/img2oss
docker save -o img2oss.tar odinluo/img2oss:latest
move img2oss.tar \\10.0.0.1\docker\images