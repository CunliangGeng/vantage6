FROM debian:10

RUN apt update
RUN apt upgrade -y

RUN apt install -y openssh-server

RUN mkdir /app

COPY services/ssh-tunnel/ /app/
RUN chmod +x /app/entry.sh

ENTRYPOINT ["/app/entry.sh"]