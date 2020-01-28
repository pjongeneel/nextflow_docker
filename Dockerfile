FROM phusion/baseimage:0.11

RUN apt-get update && apt-get install -y \
    python-minimal \
    wget

RUN wget -qO- https://get.nextflow.io | bash