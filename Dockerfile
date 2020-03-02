FROM phusion/baseimage:0.11

RUN apt-get update && apt-get install -y \
    python-minimal \
    wget \
    default-jre

RUN wget -qO- https://get.nextflow.io | bash
RUN mv nextflow /usr/local/bin
COPY nextflow.aws.sh /opt/bin/nextflow.aws.sh
RUN chmod +x /opt/bin/nextflow.aws.sh
WORKDIR /opt/work
ENTRYPOINT ["/opt/bin/nextflow.aws.sh"]
