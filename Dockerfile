FROM phusion/baseimage:0.11

# Install debian dependencies
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    default-jre=2:1.11-68ubuntu1~18.04.1 \
    python3-minimal=3.6.7-1~18.04 \
    python3-pip=9.0.1-2.3~ubuntu1.18.04.1 \
    python3-setuptools=39.0.1-2 \
    wget=1.19.4-1ubuntu2.2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install boto3
RUN python3 -m pip install pip --upgrade \
    && python3 -m pip install boto3 --upgrade

RUN wget -qO- https://get.nextflow.io | bash
RUN mv nextflow /usr/local/bin
COPY nextflow.aws.sh /opt/bin/nextflow.aws.sh
RUN chmod +x /opt/bin/nextflow.aws.sh
WORKDIR /opt/work
ENTRYPOINT ["/opt/bin/nextflow.aws.sh"]
